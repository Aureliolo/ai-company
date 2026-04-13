package proxy

import (
	"context"
	"fmt"
	"io"
	"net"
	"sync"
	"sync/atomic"
	"time"

	"github.com/Aureliolo/synthorg/sidecar/internal/allowlist"
)

const dialTimeout = 5 * time.Second

// Logger is the minimal logging interface used by the proxy.
type Logger interface {
	Info(msg string, kvs ...any)
	Warn(msg string, kvs ...any)
	Error(msg string, kvs ...any)
}

// Proxy is a transparent TCP proxy that enforces an allowlist.
type Proxy struct {
	port     uint16
	al       *allowlist.Allowlist
	allowAll atomic.Bool
	dnat     *DNATManager
	logger   Logger

	listener net.Listener
	wg       sync.WaitGroup
	done     chan struct{}
}

// New creates a transparent TCP proxy.
func New(port uint16, al *allowlist.Allowlist, allowAll bool, dnat *DNATManager, logger Logger) *Proxy {
	p := &Proxy{
		port:   port,
		al:     al,
		dnat:   dnat,
		logger: logger,
		done:   make(chan struct{}),
	}
	p.allowAll.Store(allowAll)
	return p
}

// Start begins accepting TCP connections.
func (p *Proxy) Start() error {
	ln, err := net.Listen("tcp", fmt.Sprintf("0.0.0.0:%d", p.port))
	if err != nil {
		return fmt.Errorf("proxy listen: %w", err)
	}
	p.listener = ln
	go p.acceptLoop()
	return nil
}

// Shutdown gracefully shuts down the proxy, draining active connections.
func (p *Proxy) Shutdown(ctx context.Context) error {
	close(p.done)
	if p.listener != nil {
		_ = p.listener.Close()
	}

	waitCh := make(chan struct{})
	go func() {
		p.wg.Wait()
		close(waitCh)
	}()

	select {
	case <-waitCh:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// SetAllowAll dynamically toggles allow-all mode.
func (p *Proxy) SetAllowAll(v bool) {
	p.allowAll.Store(v)
}

func (p *Proxy) acceptLoop() {
	for {
		conn, err := p.listener.Accept()
		if err != nil {
			select {
			case <-p.done:
				return
			default:
				if p.logger != nil {
					p.logger.Error("proxy.accept.error", "error", err.Error())
				}
				continue
			}
		}
		p.wg.Add(1)
		go func() {
			defer p.wg.Done()
			p.handleConn(conn)
		}()
	}
}

func (p *Proxy) handleConn(conn net.Conn) {
	defer conn.Close()

	destIP, destPort, err := GetOriginalDst(conn)
	if err != nil {
		if p.logger != nil {
			p.logger.Error("proxy.original_dst.failed", "error", err.Error())
		}
		return
	}

	// Check allowlist.
	if !p.allowAll.Load() && !p.al.IsAllowedIP(destIP, destPort) {
		if p.logger != nil {
			p.logger.Info("proxy.connection.blocked",
				"dst_ip", destIP, "dst_port", destPort,
				"reason", "not in allowlist",
			)
		}
		return
	}

	if p.allowAll.Load() && p.logger != nil {
		p.logger.Warn("proxy.connection.allow_all",
			"dst_ip", destIP, "dst_port", destPort,
		)
	} else if p.logger != nil {
		p.logger.Info("proxy.connection.allowed",
			"dst_ip", destIP, "dst_port", destPort,
		)
	}

	// Dial upstream.
	upstream, err := net.DialTimeout("tcp",
		fmt.Sprintf("%s:%d", destIP, destPort), dialTimeout)
	if err != nil {
		if p.logger != nil {
			p.logger.Error("proxy.dial.failed",
				"dst_ip", destIP, "dst_port", destPort,
				"error", err.Error(),
			)
		}
		return
	}
	defer upstream.Close()

	// Bidirectional copy.
	var copyWg sync.WaitGroup
	copyWg.Add(1)
	go func() {
		defer copyWg.Done()
		_, _ = io.Copy(upstream, conn)
		// Signal the other direction to stop.
		if tc, ok := upstream.(*net.TCPConn); ok {
			_ = tc.CloseWrite()
		}
	}()
	_, _ = io.Copy(conn, upstream)
	if tc, ok := conn.(*net.TCPConn); ok {
		_ = tc.CloseWrite()
	}
	copyWg.Wait()
}

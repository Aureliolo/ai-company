package proxy

import (
	"context"
	"fmt"
	"io"
	"net"
	"sync"
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
// Allow-all state is owned by the Allowlist (updated atomically via
// the admin API) -- the proxy does not keep a separate copy.
type Proxy struct {
	port   uint16
	al     *allowlist.Allowlist
	dnat   *DNATManager
	logger Logger

	listener net.Listener
	wg       sync.WaitGroup
	done     chan struct{}
}

// New creates a transparent TCP proxy. The allow-all state is read
// from the Allowlist at connection time so admin API updates take
// effect immediately.
func New(port uint16, al *allowlist.Allowlist, dnat *DNATManager, logger Logger) *Proxy {
	return &Proxy{
		port:   port,
		al:     al,
		dnat:   dnat,
		logger: logger,
		done:   make(chan struct{}),
	}
}

// Start begins accepting TCP connections.
func (p *Proxy) Start() error {
	ln, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", p.port))
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

	// Check allowlist (includes allow-all check internally).
	if !p.al.IsAllowedIP(destIP, destPort) {
		if p.logger != nil {
			p.logger.Info("proxy.connection.blocked",
				"dst_ip", destIP, "dst_port", destPort,
				"reason", "not in allowlist",
			)
		}
		// Send TCP RST instead of graceful close so the sandbox
		// gets an immediate connection refused, not a timeout.
		if tc, ok := conn.(*net.TCPConn); ok {
			_ = tc.SetLinger(0)
		}
		return
	}

	if p.al.IsAllowAll() && p.logger != nil {
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
		if _, err := io.Copy(upstream, conn); err != nil && p.logger != nil {
			p.logger.Warn("proxy.copy.upstream.error", "error", err.Error())
		}
		// Signal the other direction to stop.
		if tc, ok := upstream.(*net.TCPConn); ok {
			_ = tc.CloseWrite()
		}
	}()
	if _, err := io.Copy(conn, upstream); err != nil && p.logger != nil {
		p.logger.Warn("proxy.copy.downstream.error", "error", err.Error())
	}
	if tc, ok := conn.(*net.TCPConn); ok {
		_ = tc.CloseWrite()
	}
	copyWg.Wait()
}

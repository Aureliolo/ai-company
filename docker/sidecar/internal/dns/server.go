// Package dns provides a DNS server that enforces the allowlist.
// Allowed hostnames are forwarded to upstream DNS; denied ones get NXDOMAIN.
package dns

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"net"
	"os"
	"strings"
	"sync"

	"github.com/Aureliolo/synthorg/sidecar/internal/allowlist"
)

// Logger is the minimal logging interface.
type Logger interface {
	Info(msg string, kvs ...any)
	Warn(msg string, kvs ...any)
	Error(msg string, kvs ...any)
}

// Server is a DNS server that filters queries based on the allowlist.
type Server struct {
	al         *allowlist.Allowlist
	dnsAllowed bool
	logger     Logger
	udpConn    *net.UDPConn
	tcpLn      net.Listener
	upstream   string
	done       chan struct{}
	wg         sync.WaitGroup
}

// NewServer creates a DNS server.
func NewServer(al *allowlist.Allowlist, dnsAllowed bool, logger Logger) *Server {
	return &Server{
		al:         al,
		dnsAllowed: dnsAllowed,
		logger:     logger,
		upstream:   findUpstreamDNS(),
		done:       make(chan struct{}),
	}
}

// Start begins listening on UDP and TCP port 53.
func (s *Server) Start() error {
	udpAddr := &net.UDPAddr{Port: 53}
	udpConn, err := net.ListenUDP("udp", udpAddr)
	if err != nil {
		return fmt.Errorf("dns udp listen: %w", err)
	}
	s.udpConn = udpConn

	tcpLn, err := net.Listen("tcp", ":53")
	if err != nil {
		udpConn.Close()
		return fmt.Errorf("dns tcp listen: %w", err)
	}
	s.tcpLn = tcpLn

	s.wg.Add(2)
	go func() {
		defer s.wg.Done()
		s.serveUDP()
	}()
	go func() {
		defer s.wg.Done()
		s.serveTCP()
	}()

	return nil
}

// Stop shuts down the DNS server.
func (s *Server) Stop() {
	select {
	case <-s.done:
		return
	default:
		close(s.done)
	}
	if s.udpConn != nil {
		s.udpConn.Close()
	}
	if s.tcpLn != nil {
		s.tcpLn.Close()
	}
	s.wg.Wait()
}

func (s *Server) serveUDP() {
	buf := make([]byte, 4096)
	for {
		n, addr, err := s.udpConn.ReadFromUDP(buf)
		if err != nil {
			select {
			case <-s.done:
				return
			default:
				continue
			}
		}
		query := make([]byte, n)
		copy(query, buf[:n])
		go s.handleUDP(query, addr)
	}
}

func (s *Server) serveTCP() {
	for {
		conn, err := s.tcpLn.Accept()
		if err != nil {
			select {
			case <-s.done:
				return
			default:
				continue
			}
		}
		go s.handleTCP(conn)
	}
}

func (s *Server) handleUDP(query []byte, addr *net.UDPAddr) {
	resp := s.processQuery(query)
	if resp != nil {
		_, _ = s.udpConn.WriteToUDP(resp, addr)
	}
}

func (s *Server) handleTCP(conn net.Conn) {
	defer conn.Close()
	reader := bufio.NewReader(conn)

	// TCP DNS: 2-byte length prefix.
	var lenBuf [2]byte
	if _, err := reader.Read(lenBuf[:]); err != nil {
		return
	}
	msgLen := binary.BigEndian.Uint16(lenBuf[:])
	query := make([]byte, msgLen)
	if _, err := reader.Read(query); err != nil {
		return
	}

	resp := s.processQuery(query)
	if resp == nil {
		return
	}

	// Write response with length prefix.
	binary.BigEndian.PutUint16(lenBuf[:], uint16(len(resp)))
	_, _ = conn.Write(lenBuf[:])
	_, _ = conn.Write(resp)
}

func (s *Server) processQuery(query []byte) []byte {
	hostname := extractQueryHostname(query)
	if hostname == "" {
		// Can't parse -- forward as-is.
		return s.forwardToUpstream(query)
	}

	if s.al.IsAllowedHostname(hostname) {
		if s.logger != nil {
			s.logger.Info("dns.query.allowed", "host", hostname)
		}
		return s.forwardToUpstream(query)
	}

	if s.logger != nil {
		s.logger.Info("dns.query.denied", "host", hostname, "reason", "not in allowlist")
	}
	return buildNXDOMAIN(query)
}

func (s *Server) forwardToUpstream(query []byte) []byte {
	if s.upstream == "" {
		return buildNXDOMAIN(query)
	}

	conn, err := net.Dial("udp", s.upstream)
	if err != nil {
		return buildNXDOMAIN(query)
	}
	defer conn.Close()

	if _, err := conn.Write(query); err != nil {
		return buildNXDOMAIN(query)
	}

	buf := make([]byte, 4096)
	n, err := conn.Read(buf)
	if err != nil {
		return buildNXDOMAIN(query)
	}
	resp := make([]byte, n)
	copy(resp, buf[:n])
	return resp
}

// ExtractQueryHostname extracts the queried hostname from a DNS query.
// Returns empty string if the query can't be parsed.
func ExtractQueryHostname(query []byte) string {
	return extractQueryHostname(query)
}

func extractQueryHostname(query []byte) string {
	// DNS header is 12 bytes.
	if len(query) < 13 {
		return ""
	}

	// Question section starts at byte 12.
	pos := 12
	var parts []string
	for pos < len(query) {
		length := int(query[pos])
		if length == 0 {
			break
		}
		pos++
		if pos+length > len(query) {
			return ""
		}
		parts = append(parts, string(query[pos:pos+length]))
		pos += length
	}
	if len(parts) == 0 {
		return ""
	}
	return strings.ToLower(strings.Join(parts, "."))
}

// BuildNXDOMAIN creates a minimal NXDOMAIN response for the given query.
func BuildNXDOMAIN(query []byte) []byte {
	return buildNXDOMAIN(query)
}

func buildNXDOMAIN(query []byte) []byte {
	if len(query) < 12 {
		return nil
	}
	resp := make([]byte, len(query))
	copy(resp, query)

	// Set QR=1 (response), RCODE=3 (NXDOMAIN).
	resp[2] = 0x81 // QR=1, RD=1
	resp[3] = 0x83 // RA=1, RCODE=3 (NXDOMAIN)

	// Zero answer, authority, additional counts.
	resp[6] = 0
	resp[7] = 0
	resp[8] = 0
	resp[9] = 0
	resp[10] = 0
	resp[11] = 0

	return resp
}

// findUpstreamDNS reads /etc/resolv.conf for the first nameserver.
func findUpstreamDNS() string {
	f, err := os.Open("/etc/resolv.conf")
	if err != nil {
		return "8.8.8.8:53"
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if strings.HasPrefix(line, "nameserver") {
			fields := strings.Fields(line)
			if len(fields) >= 2 {
				return fields[1] + ":53"
			}
		}
	}
	return "8.8.8.8:53"
}

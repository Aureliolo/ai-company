// Package proxy implements the transparent TCP proxy with DNAT support.
package proxy

import (
	"context"
	"fmt"
	"net"
	"os/exec"
	"strings"
	"sync"
)

// DNATManager installs and cleans up iptables DNAT rules for
// transparent TCP interception.
type DNATManager struct {
	proxyPort  uint16
	dnsAllowed bool

	mu    sync.Mutex
	rules []string // installed rules for cleanup
}

// NewDNATManager creates a DNAT manager for the given proxy port.
func NewDNATManager(proxyPort uint16, dnsAllowed bool) *DNATManager {
	return &DNATManager{
		proxyPort:  proxyPort,
		dnsAllowed: dnsAllowed,
	}
}

// Setup installs iptables DNAT rules to redirect all outbound TCP
// (except loopback) to the proxy listener.
func (m *DNATManager) Setup(ctx context.Context) error {
	// Verify iptables is available.
	if err := exec.CommandContext(ctx, "iptables", "-V").Run(); err != nil {
		return fmt.Errorf("iptables unavailable (NET_ADMIN required): %w", err)
	}

	// Redirect all non-loopback TCP OUTPUT to the proxy.
	mainRule := fmt.Sprintf(
		"-t nat -A OUTPUT -p tcp ! -d 127.0.0.0/8 -j DNAT --to-destination 127.0.0.1:%d",
		m.proxyPort,
	)
	if err := m.installRule(ctx, mainRule); err != nil {
		return fmt.Errorf("DNAT rule: %w", err)
	}

	// Block DNS if not allowed.
	if !m.dnsAllowed {
		for _, proto := range []string{"udp", "tcp"} {
			dnsRule := fmt.Sprintf("-A OUTPUT -p %s --dport 53 -j DROP", proto)
			if err := m.installRule(ctx, dnsRule); err != nil {
				return fmt.Errorf("DNS block rule (%s): %w", proto, err)
			}
		}
	}

	// Drop IPv6 OUTPUT unconditionally (IPv4 only).
	_ = exec.CommandContext(ctx, "ip6tables", "-P", "OUTPUT", "DROP").Run()

	return nil
}

// Cleanup removes all installed iptables rules (reverse order).
func (m *DNATManager) Cleanup(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	var firstErr error
	for i := len(m.rules) - 1; i >= 0; i-- {
		delRule := strings.Replace(m.rules[i], " -A ", " -D ", 1)
		args := strings.Fields(delRule)
		if err := exec.CommandContext(ctx, "iptables", args...).Run(); err != nil {
			if firstErr == nil {
				firstErr = fmt.Errorf("cleanup rule %q: %w", delRule, err)
			}
		}
	}
	m.rules = nil
	return firstErr
}

// Rules returns the currently installed rules (for testing/debugging).
func (m *DNATManager) Rules() []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	out := make([]string, len(m.rules))
	copy(out, m.rules)
	return out
}

func (m *DNATManager) installRule(ctx context.Context, rule string) error {
	args := strings.Fields(rule)
	if err := exec.CommandContext(ctx, "iptables", args...).Run(); err != nil {
		return err
	}
	m.mu.Lock()
	m.rules = append(m.rules, rule)
	m.mu.Unlock()
	return nil
}

// GetOriginalDst extracts the original destination address from a
// DNAT-redirected TCP connection using SO_ORIGINAL_DST.
// This is Linux-specific and requires the connection to have been
// redirected by an iptables DNAT rule.
func GetOriginalDst(conn net.Conn) (ip string, port uint16, err error) {
	return getOriginalDst(conn)
}

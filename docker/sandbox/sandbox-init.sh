#!/bin/sh
# Sandbox entrypoint -- enforces allowed_hosts via iptables, then drops
# to the unprivileged sandbox user.
#
# Environment variables (set by DockerSandbox._apply_network_enforcement):
#   SANDBOX_ALLOWED_HOSTS    - comma-separated host:port pairs
#   SANDBOX_DNS_ALLOWED      - "1" to allow outbound DNS (port 53)
#   SANDBOX_LOOPBACK_ALLOWED - "1" to allow loopback traffic
#
# Limitations:
#   - Only IPv4 and TCP traffic is allowed to host:port pairs.
#     IPv6 OUTPUT is unconditionally dropped when enforcement is active.
#   - Hostnames are resolved to IPv4 addresses at container startup;
#     subsequent DNS changes (CDN rotation, geo-DNS) are not reflected
#     in the iptables rules.  Use stable IPs for production allowed_hosts.
#   - NET_ADMIN capability is granted at the container level for iptables
#     setup. setpriv clears bounding/ambient/inheritable sets before
#     executing the user command, but the container-level grant persists
#     (Docker limitation -- cannot drop capabilities mid-lifecycle).
set -eu

# POSIX-compatible error trap: EXIT fires on any exit (including set -e
# failures).  We capture $? and emit a diagnostic only on non-zero.
trap 'rc=$?; if [ "$rc" -ne 0 ]; then echo "sandbox-init: FATAL: iptables setup failed (exit $rc)" >&2; fi' EXIT

if [ -n "${SANDBOX_ALLOWED_HOSTS:-}" ]; then
  # Disable globbing to prevent wildcard expansion in unquoted variables.
  set -f

  # Set up ALLOW rules first, before setting the DROP default policy.
  # This avoids any window where traffic is dropped before rules are
  # in place.

  if [ "${SANDBOX_LOOPBACK_ALLOWED:-1}" = "1" ]; then
    iptables -A OUTPUT -o lo -j ACCEPT
  fi

  # No ESTABLISHED,RELATED rule on OUTPUT -- explicit destination rules
  # already cover all legitimate outbound traffic.  An OUTPUT
  # ESTABLISHED rule would allow the container to respond to any
  # externally initiated connection, widening the policy.
  # Return traffic for outbound TCP connections (SYN-ACK etc.) enters
  # via INPUT (default ACCEPT) and needs no OUTPUT rule.

  # Allow DNS only to the container's configured nameservers (from
  # /etc/resolv.conf), not to arbitrary destinations.  This prevents
  # DNS tunneling exfiltration while still allowing hostname resolution.
  if [ "${SANDBOX_DNS_ALLOWED:-1}" = "1" ]; then
    awk '/^nameserver/{print $2}' /etc/resolv.conf | while IFS= read -r ns; do
      iptables -A OUTPUT -d "$ns" -p udp --dport 53 -j ACCEPT
      iptables -A OUTPUT -d "$ns" -p tcp --dport 53 -j ACCEPT
    done
  fi

  # Allow each host:port pair (TCP only, IPv4 only).
  any_resolved=0
  IFS=','
  for entry in $SANDBOX_ALLOWED_HOSTS; do
    host="${entry%%:*}"
    port="${entry#*:}"
    # Defense-in-depth: validate port is numeric (primary gate is Python).
    case "$port" in
      *[!0-9]*) echo "sandbox-init: ERROR: invalid port '$port' in '$entry' -- skipping" >&2; continue ;;
    esac
    # Use ahostsv4 to get only IPv4 addresses (iptables is IPv4 only).
    resolved_ips=$(getent ahostsv4 "$host" 2>/dev/null | awk '{print $1}' | sort -u)
    if [ -z "$resolved_ips" ]; then
      echo "sandbox-init: WARNING: could not resolve host '$host' -- no rule added" >&2
    else
      any_resolved=1
    fi
    for ip in $resolved_ips; do
      # Verify the resolved value looks like an IPv4 address.
      case "$ip" in
        *[!0-9.]*) echo "sandbox-init: WARNING: skipping non-IPv4 '$ip' for '$host'" >&2; continue ;;
      esac
      iptables -A OUTPUT -d "$ip" -p tcp --dport "$port" -j ACCEPT
    done
  done
  unset IFS

  if [ "$any_resolved" = "0" ]; then
    echo "sandbox-init: FATAL: none of the allowed_hosts could be resolved" >&2
    exit 1
  fi

  # Restore globbing.
  set +f

  # Default DROP for both IPv4 and IPv6 -- applied AFTER all allow
  # rules are in place.  IPv6 is unconditionally dropped since only
  # IPv4 iptables rules are configured.
  iptables -P OUTPUT DROP
  ip6tables -P OUTPUT DROP 2>/dev/null || true
fi

# Clear the EXIT trap before exec so a successful run does not trigger it.
trap - EXIT

# Drop to sandbox user and clear all capability sets.
# IMPORTANT: UID must match useradd --uid in docker/sandbox/Dockerfile.
exec setpriv --reuid=10001 --regid=10001 --init-groups \
     --inh-caps=-all --ambient-caps=-all --bounding-set=-all -- "$@"

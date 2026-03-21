#!/bin/sh
# Sandbox entrypoint -- enforces allowed_hosts via iptables, then drops
# to the unprivileged sandbox user.
#
# Environment variables (set by DockerSandbox._build_container_config):
#   SANDBOX_ALLOWED_HOSTS    - comma-separated host:port pairs
#   SANDBOX_DNS_ALLOWED      - "1" to allow outbound DNS (port 53)
#   SANDBOX_LOOPBACK_ALLOWED - "1" to allow loopback traffic
#
# Limitations:
#   - Only TCP traffic is allowed to host:port pairs (UDP is not supported).
#   - Hostnames are resolved to IPs at container startup; subsequent DNS
#     changes (CDN rotation, geo-DNS) are not reflected in the iptables rules.
#     Use stable IPs or CIDR ranges for production allowed_hosts.
#   - NET_ADMIN/NET_RAW capabilities are granted at the container level for
#     iptables setup. setpriv clears bounding/ambient/inheritable sets before
#     executing the user command, but the container-level grant persists
#     (Docker limitation -- cannot drop capabilities mid-lifecycle).
set -eu

if [ -n "${SANDBOX_ALLOWED_HOSTS:-}" ]; then
  # Disable globbing to prevent wildcard expansion in unquoted variables.
  set -f

  # Set up ALLOW rules first, before setting the DROP default policy.
  # This avoids any window where traffic is dropped before rules are
  # in place.

  if [ "${SANDBOX_LOOPBACK_ALLOWED:-1}" = "1" ]; then
    iptables -A OUTPUT -o lo -j ACCEPT
  fi

  # Allow established/related connections (replies to allowed outbound).
  iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

  # Allow DNS only to the container's configured nameservers (from
  # /etc/resolv.conf), not to arbitrary destinations.  This prevents
  # DNS tunneling exfiltration while still allowing hostname resolution.
  if [ "${SANDBOX_DNS_ALLOWED:-1}" = "1" ]; then
    for ns in $(awk '/^nameserver/{print $2}' /etc/resolv.conf); do
      iptables -A OUTPUT -d "$ns" -p udp --dport 53 -j ACCEPT
      iptables -A OUTPUT -d "$ns" -p tcp --dport 53 -j ACCEPT
    done
  fi

  # Allow each host:port pair (TCP only).
  IFS=','
  for entry in $SANDBOX_ALLOWED_HOSTS; do
    host="${entry%%:*}"
    port="${entry#*:}"
    resolved_ips=$(getent hosts "$host" 2>/dev/null | awk '{print $1}')
    if [ -z "$resolved_ips" ]; then
      echo "sandbox-init: WARNING: could not resolve host '$host' -- no rule added" >&2
    fi
    for ip in $resolved_ips; do
      iptables -A OUTPUT -d "$ip" -p tcp --dport "$port" -j ACCEPT
    done
  done
  unset IFS

  # Default DROP -- applied AFTER all allow rules are in place.
  iptables -P OUTPUT DROP
fi

# Drop to sandbox user (UID 10001) and clear all capability sets.
exec setpriv --reuid=10001 --regid=10001 --init-groups \
     --inh-caps=-all --ambient-caps=-all --bounding-set=-all -- "$@"

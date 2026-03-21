#!/bin/sh
# Sandbox entrypoint -- enforces allowed_hosts via iptables, then drops
# to the unprivileged sandbox user.
#
# Environment variables (set by DockerSandbox._build_container_config):
#   SANDBOX_ALLOWED_HOSTS  - comma-separated host:port pairs
#   SANDBOX_DNS_ALLOWED    - "1" to allow outbound DNS (port 53)
#   SANDBOX_LOOPBACK_ALLOWED - "1" to allow loopback traffic
set -eu

if [ -n "${SANDBOX_ALLOWED_HOSTS:-}" ]; then
  # Set up ALLOW rules first, before setting the DROP default policy.
  # This avoids any window where traffic is dropped before rules are
  # in place.

  if [ "${SANDBOX_LOOPBACK_ALLOWED:-1}" = "1" ]; then
    iptables -A OUTPUT -o lo -j ACCEPT
  fi

  # Allow established/related connections (replies to allowed outbound).
  iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

  if [ "${SANDBOX_DNS_ALLOWED:-1}" = "1" ]; then
    iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
  fi

  # Allow each host:port pair.
  IFS=','
  for entry in $SANDBOX_ALLOWED_HOSTS; do
    host="${entry%%:*}"
    port="${entry#*:}"
    for ip in $(getent hosts "$host" 2>/dev/null | awk '{print $1}'); do
      iptables -A OUTPUT -d "$ip" -p tcp --dport "$port" -j ACCEPT
    done
  done
  unset IFS

  # Default DROP -- applied AFTER all allow rules are in place.
  iptables -P OUTPUT DROP
fi

# Drop to sandbox user (UID 10001) and clear inherited capabilities.
exec setpriv --reuid=10001 --regid=10001 --init-groups --inh-caps=-all -- "$@"

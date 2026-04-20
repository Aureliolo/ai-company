import type { TaskStatus } from '@/api/types/enums'
import {
  TASK_STATUS_ORDER,
  TERMINAL_STATUSES,
  VALID_TRANSITIONS,
  WRITE_ROLES,
  WS_RECONNECT_BASE_DELAY,
  WS_RECONNECT_MAX_DELAY,
  WS_MAX_RECONNECT_ATTEMPTS,
  WS_MAX_MESSAGE_SIZE,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  MIN_PASSWORD_LENGTH,
  LOGIN_MAX_ATTEMPTS,
  LOGIN_LOCKOUT_MS,
  NAMESPACE_ORDER,
  NAMESPACE_DISPLAY_NAMES,
} from '@/utils/constants'

describe('constants', () => {
  describe('WebSocket constants', () => {
    it('has sane reconnect defaults', () => {
      expect(WS_RECONNECT_BASE_DELAY).toBe(1000)
      expect(WS_RECONNECT_MAX_DELAY).toBe(30000)
      expect(WS_MAX_RECONNECT_ATTEMPTS).toBe(20)
      expect(WS_MAX_MESSAGE_SIZE).toBe(131072)
    })
  })

  describe('pagination constants', () => {
    it('has sane page size defaults', () => {
      expect(DEFAULT_PAGE_SIZE).toBeLessThanOrEqual(MAX_PAGE_SIZE)
      expect(DEFAULT_PAGE_SIZE).toBeGreaterThan(0)
    })
  })

  describe('login constants', () => {
    it('has sane login lockout defaults', () => {
      expect(LOGIN_MAX_ATTEMPTS).toBeGreaterThan(0)
      expect(LOGIN_LOCKOUT_MS).toBeGreaterThan(0)
      expect(MIN_PASSWORD_LENGTH).toBeGreaterThanOrEqual(8)
    })
  })

  describe('WRITE_ROLES', () => {
    it('contains expected roles', () => {
      expect(WRITE_ROLES).toContain('ceo')
      expect(WRITE_ROLES).toContain('manager')
      expect(WRITE_ROLES).toContain('pair_programmer')
      expect(WRITE_ROLES).not.toContain('board_member')
      expect(WRITE_ROLES).not.toContain('observer')
      expect(WRITE_ROLES).not.toContain('system')
      expect(WRITE_ROLES).toHaveLength(3)
    })
  })

  describe('TASK_STATUS_ORDER', () => {
    it('contains all statuses from VALID_TRANSITIONS', () => {
      const transitionKeys = Object.keys(VALID_TRANSITIONS) as TaskStatus[]
      for (const status of transitionKeys) {
        expect(TASK_STATUS_ORDER).toContain(status)
      }
    })

    it('has no duplicates', () => {
      const unique = new Set(TASK_STATUS_ORDER)
      expect(unique.size).toBe(TASK_STATUS_ORDER.length)
    })
  })

  describe('VALID_TRANSITIONS', () => {
    it('terminal statuses have no transitions', () => {
      for (const status of TERMINAL_STATUSES) {
        expect(VALID_TRANSITIONS[status]).toHaveLength(0)
      }
    })

    it('all transition targets are valid statuses', () => {
      const allStatuses = new Set(TASK_STATUS_ORDER)
      for (const targets of Object.values(VALID_TRANSITIONS)) {
        for (const target of targets) {
          expect(allStatuses.has(target)).toBe(true)
        }
      }
    })

    it('non-terminal statuses have at least one transition', () => {
      for (const [status, targets] of Object.entries(VALID_TRANSITIONS)) {
        if (!TERMINAL_STATUSES.has(status as TaskStatus)) {
          expect(targets.length).toBeGreaterThan(0)
        }
      }
    })
  })

  describe('NAMESPACE_ORDER', () => {
    it('excludes company and providers (they have dedicated pages)', () => {
      expect(NAMESPACE_ORDER).not.toContain('company')
      expect(NAMESPACE_ORDER).not.toContain('providers')
    })

    it('every namespace in order has a display name', () => {
      for (const ns of NAMESPACE_ORDER) {
        expect(NAMESPACE_DISPLAY_NAMES[ns]).toBeDefined()
      }
    })
  })
})

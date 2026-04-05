/**
 * Shared "Coming soon" copy + issue pointer for the Edit Organization
 * and Org Chart write paths.
 *
 * The backend does not yet expose CRUD endpoints for company /
 * departments / agents -- every mutation path in `web/src/api/endpoints/
 * company.ts` returns 405 Method Not Allowed.  Until that gap closes,
 * the dashboard disables every write affordance and surfaces this
 * module's copy in tooltips + banners so operators do not hit silent
 * 405s.
 *
 * When issue #1081 lands, delete this file and remove every import of
 * it -- a single grep for `coming-soon` (or `1081`) will surface all
 * the gates that need to come off.
 */

export const ORG_EDIT_COMING_SOON_ISSUE = 1081

export const ORG_EDIT_COMING_SOON_URL =
  'https://github.com/Aureliolo/synthorg/issues/1081'

/** Short form used inside HTML `title` attributes and button labels. */
export const ORG_EDIT_COMING_SOON_TOOLTIP =
  'Editing organization structure is not yet available -- backend CRUD endpoints pending (#1081).'

/** Longer form used in banners and empty-state descriptions. */
export const ORG_EDIT_COMING_SOON_DESCRIPTION =
  'Saving, creating, deleting, and reordering departments or agents is temporarily disabled because the backend CRUD endpoints have not yet been implemented. You can still view the current organization and apply template packs. Progress is tracked in issue #1081.'

/**
 * MSW request handlers for Storybook API mocking.
 *
 * Usage in stories:
 *   import { setupStatusComplete } from '@/mocks/handlers'
 *
 *   export const MyStory: Story = {
 *     parameters: {
 *       msw: { handlers: [...setupStatusComplete] },
 *     },
 *   }
 *
 * Each export is an array of RequestHandler objects. Spread them into
 * parameters.msw.handlers -- the mswLoader (configured in preview.tsx)
 * activates them before the story renders (resetting any prior handlers first).
 *
 * All responses use the ApiResponse<T> envelope via apiSuccess() / apiError() helpers.
 */

export { apiError, apiSuccess } from './helpers'
export { setupStatusComplete, setupStatusNeedsAdmin } from './setup'
export { authLoginSuccess, authSetupSuccess } from './auth'
export { artifactsList } from './artifacts'
export { projectsList } from './projects'
export { templatePacksList } from './template-packs'

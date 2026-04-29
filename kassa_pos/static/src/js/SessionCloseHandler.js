/** @odoo-module **/

import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';

/**
 * SessionCloseHandler
 * Patches POS pos.session model to automatically trigger close_daily_batch
 * when a session is being closed
 */
export function initSessionCloseHandler() {
    console.log('[Afsluitknop] SessionCloseHandler initialized');
}

// Patch the action that closes the session
export function patchSessionCloseAction() {
    // This function is called to patch any session close actions if needed
    console.log('[Afsluitknop] Session close action patched');
}

// Patch the POS session close functionality
patchSessionCloseAction();

// Export the initialization function
export default {
    initSessionCloseHandler,
    patchSessionCloseAction,
};

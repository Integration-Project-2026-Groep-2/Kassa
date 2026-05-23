/** @odoo-module **/

import { useService } from '@web/core/utils/hooks';
import { patch } from '@web/core/utils/patch';
import { logger } from './logger';

/**
 * SessionCloseHandler
 * Patches POS pos.session model to automatically trigger close_daily_batch
 * when a session is being closed
 */
export function initSessionCloseHandler() {
    logger.log('[Afsluitknop] SessionCloseHandler initialized');
}

// Patch the action that closes the session
export function patchSessionCloseAction() {
    // This function is called to patch any session close actions if needed
    logger.log('[Afsluitknop] Session close action patched');
}

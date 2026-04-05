/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Component, xml } from "@odoo/owl";
import { UserRegistrationModal } from "./UserRegistration";

/**
 * Simple Dialog Opener Component
 */
class DialogOpener {
    static instance = null;
    static dialogService = null;

    static setDialogService(dialog) {
        console.log('DialogOpener: Setting dialog service', dialog);
        this.dialogService = dialog;
    }

    static openUserModal() {
        console.log('DialogOpener.openUserModal called');
        console.log('DialogOpener.dialogService:', this.dialogService);
        
        if (this.dialogService) {
            try {
                console.log('Opening UserRegistrationModal...');
                const close = this.dialogService.add(UserRegistrationModal, {});
                console.log('Modal opened successfully, close function:', close);
                return close;
            } catch (err) {
                console.error('Error opening modal:', err);
                console.error('Stack:', err.stack);
                console.error('Modal component:', UserRegistrationModal);
            }
        } else {
            console.error('Dialog service not available');
            alert('User registration service is not available. Please refresh the page.');
        }
    }
}

/**
 * Patch ProductScreen to register dialog service
 */
patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        const dialog = useService('dialog');
        console.log('ProductScreen: Dialog service obtained', dialog);
        DialogOpener.setDialogService(dialog);
    },
});

/**
 * Create floating button
 */
(function initializeFloatingButton() {
    console.log('Initializing floating button...');
    
    // Create and inject styles
    const style = document.createElement('style');
    style.textContent = `
        .kassa-add-user-floating-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            padding: 12px 18px;
            background-color: #6B5CA8;
            color: white;
            border: none;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            z-index: 999;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        
        .kassa-add-user-floating-btn:hover {
            background-color: #5A4A92;
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
        }
        
        .kassa-add-user-floating-btn:active {
            transform: translateY(0);
        }
    `;
    document.head.appendChild(style);
    
    // Create button
    const button = document.createElement('button');
    button.className = 'kassa-add-user-floating-btn';
    button.innerHTML = '<i class="fa fa-user-plus" style="font-size: 16px;"></i> Add User';
    button.title = 'Register a new user';
    
    button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        console.log('Add User button clicked!');
        DialogOpener.openUserModal();
    });
    
    // Append button to body
    const addButton = () => {
        if (document.body) {
            document.body.appendChild(button);
            console.log('Floating button added to DOM');
        } else {
            setTimeout(addButton, 100);
        }
    };
    
    addButton();
    
    // Retry initializing dialog service after a delay if not available
    setTimeout(() => {
        if (!DialogOpener.dialogService) {
            console.warn('Dialog service not yet available, trying fallback...');
            try {
                const root = document.querySelector('[data-cid]') || document.querySelector('.o_web_client');
                if (root && root.__owl__) {
                    const env = root.__owl__.app.env;
                    if (env && env.services && env.services.dialog) {
                        DialogOpener.setDialogService(env.services.dialog);
                        console.log('Fallback: Dialog service obtained from DOM');
                    }
                }
            } catch (err) {
                console.warn('Fallback failed:', err);
            }
        }
    }, 2000);
})();










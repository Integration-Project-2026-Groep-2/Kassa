/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";


class UserRegistrationModal extends Component {
    static components = { Dialog };

    static template = xml`
        <Dialog title="'Register New User'" class="user-registration-modal">
            <div class="modal-header-panel">
                <div>
                    <h2>Create New POS User</h2>
                    <p class="intro-text">Add a new team member with a clean, professional interface and fast workflow.</p>
                </div>
                <span class="status-chip">Premium interface</span>
            </div>
            <div class="modal-body">
                <div t-if="uiState.hasError" class="alert alert-danger">
                    <div class="alert-message">
                        <t t-esc="uiState.errorMessage"/>
                    </div>
                </div>
                <form class="user-registration-form">
                    <div class="form-grid">
                        <div class="form-column">
                            <div class="form-group">
                                <label for="firstName" class="form-label required">First Name</label>
                                <input id="firstName" type="text" class="form-control" placeholder="Enter first name" t-model="formData.firstName" maxlength="80" required="required"/>
                            </div>
                            <div class="form-group">
                                <label for="email" class="form-label required">Email Address</label>
                                <input id="email" type="email" class="form-control" placeholder="user@example.com" t-model="formData.email" maxlength="254" required="required"/>
                            </div>
                            <div class="form-group">
                                <label for="companyId" class="form-label">Company ID</label>
                                <input id="companyId" type="text" class="form-control" placeholder="Company UUID (optional)" t-model="formData.companyId"/>
                            </div>
                        </div>
                        <div class="form-column">
                            <div class="form-group">
                                <label for="lastName" class="form-label required">Last Name</label>
                                <input id="lastName" type="text" class="form-control" placeholder="Enter last name" t-model="formData.lastName" maxlength="80" required="required"/>
                            </div>
                            <div class="form-group">
                                <label for="role" class="form-label required">Role</label>
                                <select id="role" class="form-control" t-model="formData.role" required="required">
                                    <option value="">Select a role</option>
                                    <t t-foreach="roles" t-as="role" t-key="role.value">
                                        <option t-att-value="role.value">
                                            <t t-esc="role.label"/>
                                        </option>
                                    </t>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="badgeCode" class="form-label">Badge Code</label>
                                <input id="badgeCode" type="text" class="form-control" placeholder="QR code or badge ID (optional)" t-model="formData.badgeCode"/>
                            </div>
                        </div>
                    </div>
                    <div class="section-divider">Additional Settings</div>
                    <div class="form-group form-check">
                        <input id="gdprConsent" type="checkbox" class="form-check-input" t-model="formData.gdprConsent" required="required"/>
                        <label for="gdprConsent" class="form-check-label required">I consent to GDPR data processing</label>
                    </div>
                    <div class="form-group form-check">
                        <input id="isActive" type="checkbox" class="form-check-input" t-model="formData.isActive" checked="checked"/>
                        <label for="isActive" class="form-check-label">User is active</label>
                    </div>
                </form>
            </div>
            <t t-set-slot="footer">
                <button type="button" class="btn btn-secondary" t-on-click="closeModal" t-att-disabled="uiState.isLoading">Cancel</button>
                <button type="button" class="btn btn-primary" t-on-click="onSubmit" t-att-disabled="uiState.isLoading">
                    <t t-if="uiState.isLoading">
                        <span class="spinner-border spinner-border-sm mr-2"/>
                        Creating...
                    </t>
                    <t t-else="uiState.isLoading">Create User</t>
                </button>
            </t>
        </Dialog>
    `;

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.rpc = useService('rpc');
        this.dialog = useService('dialog');
        
        console.log('UserRegistrationModal setup - dialog service:', this.dialog);
        
        // Form state
        this.formData = useState({
            firstName: '',
            lastName: '',
            email: '',
            phone: '',
            role: 'Customer',  // Default role
            companyId: '',
            badgeCode: '',
            gdprConsent: false,
            isActive: true,
        });
        
        // UI state
        this.uiState = useState({
            isLoading: false,
            hasError: false,
            errorMessage: '',
        });
        
        // Available roles for dropdown
        this.roles = [
            { value: 'Customer', label: 'Customer' },
            { value: 'Cashier', label: 'Cashier' },
            { value: 'Speaker', label: 'Speaker' },
            { value: 'EventManager', label: 'Event Manager' },
            { value: 'Admin', label: 'Admin' },
        ];
    }

    /**
     * Validate email format
     */
    isValidEmail(email) {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailPattern.test(email) && email.length <= 254;
    }

    /**
     * Validate form before submission
     */
    validateForm() {
        const { firstName, lastName, email, role, gdprConsent } = this.formData;
        
        // Check required fields
        if (!firstName.trim()) {
            this.uiState.errorMessage = 'First Name is required';
            this.uiState.hasError = true;
            return false;
        }
        
        if (firstName.length > 80) {
            this.uiState.errorMessage = 'First Name must be less than 80 characters';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!lastName.trim()) {
            this.uiState.errorMessage = 'Last Name is required';
            this.uiState.hasError = true;
            return false;
        }
        
        if (lastName.length > 80) {
            this.uiState.errorMessage = 'Last Name must be less than 80 characters';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!email.trim()) {
            this.uiState.errorMessage = 'Email is required';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!this.isValidEmail(email)) {
            this.uiState.errorMessage = 'Please enter a valid email address';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!role) {
            this.uiState.errorMessage = 'Role is required';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!gdprConsent) {
            this.uiState.errorMessage = 'GDPR consent is required';
            this.uiState.hasError = true;
            return false;
        }
        
        this.uiState.hasError = false;
        return true;
    }

    /**
     * Generate UUID v4
     */
    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0;
            const v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    /**
     * Submit form and create user
     */
    async onSubmit() {
        if (!this.validateForm()) {
            return;
        }

        this.uiState.isLoading = true;
        
        try {
            // Prepare user data
            const userId = this.generateUUID();
            const userData = {
                userId: userId,
                firstName: this.formData.firstName.trim(),
                lastName: this.formData.lastName.trim(),
                email: this.formData.email.trim(),
                phone: this.formData.phone.trim(),
                role: this.formData.role,
                companyId: this.formData.companyId.trim() || null,
                badgeCode: this.formData.badgeCode.trim() || `USER_${userId}`,
                gdprConsent: this.formData.gdprConsent,
                isActive: this.formData.isActive,
                confirmedAt: new Date().toISOString(),
            };

            // Create contact in Odoo
            const contactId = await this.orm.create('res.partner', [{
                name: `${userData.firstName} ${userData.lastName}`,
                email: userData.email,
                phone: userData.phone,
                user_id_custom: userData.userId,
                badge_code: userData.badgeCode,
                role: this.mapRoleToOdoo(userData.role),
                company_id_custom: userData.companyId,
            }]);

            console.log('User created successfully with contact ID:', contactId);

            // Success notification
            this.notification.add(`User ${userData.firstName} ${userData.lastName} created successfully!`, {
                type: 'success',
            });
            
            // Close modal
            this.closeModal();
            
        } catch (error) {
            this.uiState.errorMessage = `Error creating user: ${error.message}`;
            this.uiState.hasError = true;
            console.error('Error creating user:', error);
        } finally {
            this.uiState.isLoading = false;
        }
    }

    /**
     * Close the modal dialog
     */
    closeModal() {
        console.log('Closing modal');
        if (this.props && this.props.close) {
            this.props.close();
        }
    }

    /**
     * Map POS role to Odoo role
     */
    mapRoleToOdoo(role) {
        const roleMap = {
            'Customer': 'Customer',
            'Cashier': 'Cashier',
            'Speaker': 'Customer',
            'EventManager': 'Customer',
            'Admin': 'Admin',
        };
        return roleMap[role] || 'Customer';
    }
}
export { UserRegistrationModal };

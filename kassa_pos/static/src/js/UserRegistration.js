/** 
 * POS User Registration Modal Component
 * 
 * Odoo OWL component for the "Add User" (Nieuwe Klant) button in POS interface.
 * Provides a modal form for manual user registration when badge scanning is not available.
 * 
 * Features:
 * - Modal form with required/optional fields
 * - Client-side validation
 * - Integration with CRUD User service
 * - Fallback behavior when Integration Service is offline
 * - GDPR consent tracking
 */

const { Component, useState, useService } = owl;
const { Dialog } = require('web.OwlDialog');


class UserRegistrationModal extends Component {
    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.rpc = useService('rpc');
        
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
                customer: true,
                is_company: false,
            }]);

            // Send User message to RabbitMQ via Integration Service
            try {
                await this.rpc.call('pos.session', 'create_and_publish_user', {
                    user_data: userData,
                });
            } catch (rabbitError) {
                // Fallback: Store message for retry when service is online
                console.warn('Integration Service offline, storing message for retry:', rabbitError);
                await this.orm.create('user.message.queue', [{
                    user_id_custom: userData.userId,
                    message_type: 'UserCreated',
                    payload: JSON.stringify(userData),
                    status: 'pending',
                    retry_count: 0,
                    created_at: new Date(),
                }]);
                
                this.notification.add(
                    'User created locally. Will sync when Integration Service is available.',
                    { type: 'warning' }
                );
            }

            // Success
            this.notification.add(`User ${userData.firstName} created successfully!`, {
                type: 'success',
            });
            
            // Close modal
            this.props.close();
            
        } catch (error) {
            this.uiState.errorMessage = `Error creating user: ${error.message}`;
            this.uiState.hasError = true;
            console.error('Error creating user:', error);
        } finally {
            this.uiState.isLoading = false;
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

    /**
     * Close modal without saving
     */
    onCancel() {
        this.props.close();
    }
}

UserRegistrationModal.template = 'kassa_pos.UserRegistrationModal';


class AddUserButton extends Component {
    setup() {
        this.dialog = useService('dialog');
    }

    /**
     * Open user registration modal
     */
    openUserRegistration() {
        this.dialog.add(UserRegistrationModal, {
            title: 'Register New User',
            close: () => {}, // Called when modal is closed
        });
    }
}

AddUserButton.template = 'kassa_pos.AddUserButton';


// Register components
patch('point_of_sale.PartnerListScreen', {
    components: { ...patch.components, AddUserButton },
});


export { UserRegistrationModal, AddUserButton };

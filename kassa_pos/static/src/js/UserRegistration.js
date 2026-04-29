/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";


class UserRegistrationModal extends Component {
    static components = { Dialog };

    static template = xml`
        <Dialog title="'Nieuwe gebruiker registreren'" class="user-registration-modal">
            <div class="modal-header-panel">
                <div>
                    <h2>Nieuwe gebruiker registreren</h2>
                    <p class="intro-text">Voeg snel een nieuwe POS-gebruiker toe met een professioneel en overzichtelijk registratieformulier.</p>
                </div>
                <span class="status-badge">Live registratie</span>
            </div>

            <div class="modal-body">
                <div t-if="uiState.hasError" class="alert alert-danger">
                    <strong>Validatie mislukt:</strong>
                    <div class="alert-message">
                        <t t-esc="uiState.errorMessage"/>
                    </div>
                </div>

                <form class="user-registration-form" t-on-submit.prevent="onSubmit">
                    <div class="form-row">
                        <div class="form-column">
                            <div class="form-group">
                                <label for="firstName" class="form-label required">Voornaam</label>
                                <input id="firstName" type="text" class="form-control" placeholder="Voornaam" t-model="formData.firstName" maxlength="80" required="required"/>
                            </div>
                            <div class="form-group">
                                <label for="email" class="form-label required">E-mail</label>
                                <input id="email" type="email" class="form-control" placeholder="voorbeeld@bedrijf.com" t-model="formData.email" maxlength="254" required="required"/>
                                <small class="helper-text">Deze e-mail wordt gebruikt voor systeemcommunicatie.</small>
                            </div>
                            <div class="form-group form-check">
                                <input id="gdprConsent" type="checkbox" class="form-check-input" t-model="formData.gdprConsent" required="required"/>
                                <label for="gdprConsent" class="form-check-label required">Ik ga akkoord met GDPR-verwerking</label>
                            </div>
                        </div>
                        <div class="form-column">
                            <div class="form-group">
                                <label for="lastName" class="form-label required">Achternaam</label>
                                <input id="lastName" type="text" class="form-control" placeholder="Achternaam" t-model="formData.lastName" maxlength="80" required="required"/>
                            </div>
                            <div class="form-group">
                                <label for="role" class="form-label required">Rol</label>
                                <select id="role" class="form-control" t-model="formData.role" required="required">
                                    <option value="">Selecteer rol</option>
                                    <t t-foreach="roles" t-as="role" t-key="role.value">
                                        <option t-att-value="role.value">
                                            <t t-esc="role.label"/>
                                        </option>
                                    </t>
                                </select>
                            </div>
                            <div class="form-group form-check">
                                <input id="isActive" type="checkbox" class="form-check-input" t-model="formData.isActive" checked="checked"/>
                                <label for="isActive" class="form-check-label">Gebruiker actief</label>
                            </div>
                        </div>
                    </div>

                    <div class="section-divider">
                        <span>Extra informatie</span>
                    </div>

                    <div class="form-row">
                        <div class="form-column">
                            <div class="form-group">
                                <label for="phone" class="form-label">Telefoon</label>
                                <input id="phone" type="tel" class="form-control" placeholder="+32 123 456 789" t-model="formData.phone"/>
                                <small class="helper-text">Optioneel voor support en communicatie.</small>
                            </div>
                        </div>
                        <div class="form-column">
                            <div class="form-group">
                                <label for="companyId" class="form-label">Bedrijfs-ID</label>
                                <input id="companyId" type="text" class="form-control" placeholder="UUID van bedrijf" t-model="formData.companyId"/>
                                <small class="helper-text">Alleen invullen bij zakelijke koppelingen.</small>
                            </div>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="badgeCode" class="form-label">Badge-code</label>
                        <input id="badgeCode" type="text" class="form-control" placeholder="QR/barcode code (optioneel)" t-model="formData.badgeCode"/>
                        <small class="helper-text">Gebruik alleen als scannen niet wil werken.</small>
                    </div>
                </form>
            </div>

            <t t-set-slot="footer">
                <button type="button" class="btn btn-outline-secondary" t-on-click="closeModal" t-att-disabled="uiState.isLoading">Annuleren</button>
                <button type="button" class="btn btn-primary btn-strong" t-on-click="onSubmit" t-att-disabled="uiState.isLoading">
                    <t t-if="uiState.isLoading">
                        <span class="spinner-border spinner-border-sm mr-2"/>
                        Registreren...
                    </t>
                    <t t-else="uiState.isLoading">Gebruiker registreren</t>
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
            role: 'VISITOR',
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
            { value: 'VISITOR', label: 'Bezoeker' },
            { value: 'SPEAKER', label: 'Spreker' },
            { value: 'CASHIER', label: 'Kassier' },
            { value: 'EVENTMANAGER', label: 'Evenement Manager' },
            { value: 'ADMIN', label: 'Administrator' },
            { value: 'SPONSOR', label: 'Sponsor' },
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
            this.uiState.errorMessage = 'Voornaam is verplicht';
            this.uiState.hasError = true;
            return false;
        }
        
        if (firstName.length > 80) {
            this.uiState.errorMessage = 'Voornaam mag maximaal 80 tekens bevatten';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!lastName.trim()) {
            this.uiState.errorMessage = 'Achternaam is verplicht';
            this.uiState.hasError = true;
            return false;
        }
        
        if (lastName.length > 80) {
            this.uiState.errorMessage = 'Achternaam mag maximaal 80 tekens bevatten';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!email.trim()) {
            this.uiState.errorMessage = 'E-mail is verplicht';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!this.isValidEmail(email)) {
            this.uiState.errorMessage = 'Voer een geldig e-mailadres in';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!role) {
            this.uiState.errorMessage = 'Rol is verplicht';
            this.uiState.hasError = true;
            return false;
        }
        
        if (!gdprConsent) {
            this.uiState.errorMessage = 'GDPR-toestemming is verplicht';
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
            this.notification.add(`Gebruiker ${userData.firstName} ${userData.lastName} is succesvol aangemaakt.`, {
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

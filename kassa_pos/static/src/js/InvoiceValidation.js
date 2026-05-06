/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.rpc = useService("rpc");
        this.notification = useService("notification");
    },

    async selectPaymentMethod(paymentMethod) {
        if (!paymentMethod.name.toLowerCase().includes('invoice')) {
            return super.selectPaymentMethod(paymentMethod);
        }

        const order = this.currentOrder;
        const partner = order.get_partner();

        if (!partner) {
            this.notification.add(
                'Selecteer eerst een klant om op factuur te betalen.',
                { type: 'warning', title: 'Geen klant geselecteerd' }
            );
            return;
        }

        try {
            const result = await this.rpc('/kassa/partner/company', {
                partner_id: partner.id,
            });

            if (!result.success || !result.has_company) {
                this.notification.add(
                    `${partner.name} is niet gekoppeld aan een bedrijf. Factuurbetalingen zijn enkel mogelijk voor bedrijfsklanten.`,
                    { type: 'warning', title: 'Geen bedrijf gekoppeld' }
                );
                return;
            }

            return super.selectPaymentMethod(paymentMethod);

        } catch (e) {
            this.notification.add('Fout bij controle bedrijf: ' + e.message, { type: 'danger' });
        }
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const partner = order.get_partner();

        const invoiceLine = order.get_paymentlines().find(
            line => line.payment_method.name.toLowerCase().includes('invoice')
        );

        if (invoiceLine) {
            if (!partner) {
                this.notification.add(
                    'Selecteer een klant om op factuur te kunnen betalen.',
                    { type: 'warning', title: 'Geen klant' }
                );
                return;
            }

            try {
                const result = await this.rpc('/kassa/partner/company', {
                    partner_id: partner.id,
                });

                if (!result.success || !result.has_company) {
                    this.notification.add(
                        `${partner.name} is niet gekoppeld aan een bedrijf. Verwijder de factuurbetalingslijn om door te gaan.`,
                        { type: 'danger', title: 'Geen bedrijf gekoppeld' }
                    );
                    return;
                }

            } catch (e) {
                this.notification.add('Fout bij factuurcontrole: ' + e.message, { type: 'danger' });
                return;
            }
        }

        return super.validateOrder(isForceValidate);
    },
});

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
        if (paymentMethod.name.toLowerCase() !== 'saldo') {
            return super.selectPaymentMethod(paymentMethod);
        }

        const order = this.currentOrder;
        const partner = order.get_partner();

        if (!partner) {
            this.notification.add(
                'Selecteer eerst een klant om met saldo te betalen.',
                { type: 'warning', title: 'Geen klant geselecteerd' }
            );
            return;
        }

        try {
            const result = await this.rpc('/kassa/balance/get', {
                partner_id: partner.id,
            });

            if (!result.success || result.balance <= 0) {
                this.notification.add(
                    `${partner.name} heeft geen saldo beschikbaar.`,
                    { type: 'warning', title: 'Onvoldoende saldo' }
                );
                return;
            }

            await super.selectPaymentMethod(paymentMethod);

            const due = order.get_due();
            const maxAmount = Math.min(result.balance, due);
            const paymentLines = order.get_paymentlines();
            const saldoLine = paymentLines[paymentLines.length - 1];
            if (saldoLine && saldoLine.payment_method.name.toLowerCase() === 'saldo') {
                saldoLine.set_amount(maxAmount);
            }

            this.notification.add(
                `Beschikbaar saldo: €${result.balance.toFixed(2)} — Ingevuld: €${maxAmount.toFixed(2)}`,
                { type: 'info', title: 'Saldo' }
            );

        } catch (e) {
            this.notification.add('Fout bij ophalen saldo: ' + e.message, { type: 'danger' });
        }
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const partner = order.get_partner();

        const saldoLine = order.get_paymentlines().find(
            line => line.payment_method.name.toLowerCase() === 'saldo'
        );

        if (saldoLine) {
            if (!partner) {
                this.notification.add(
                    'Selecteer een klant om met saldo te kunnen betalen.',
                    { type: 'warning', title: 'Geen klant' }
                );
                return;
            }

            try {
                const result = await this.rpc('/kassa/balance/get', {
                    partner_id: partner.id,
                });

                const saldoBedrag = saldoLine.get_amount();

                if (!result.success || result.balance < saldoBedrag) {
                    const beschikbaar = result.success ? result.balance.toFixed(2) : '0.00';
                    this.notification.add(
                        `Onvoldoende saldo. Beschikbaar: €${beschikbaar} — Vereist: €${saldoBedrag.toFixed(2)}`,
                        { type: 'danger', title: 'Onvoldoende saldo' }
                    );
                    return;
                }
            } catch (e) {
                this.notification.add('Fout bij saldo controle: ' + e.message, { type: 'danger' });
                return;
            }
        }

        return super.validateOrder(isForceValidate);
    },
});

/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        
        // Intercept RPC calls to detect Invoice errors before they bubble up
        const notificationService = this.notification;
        const rpcService = this.rpc;
        const origCall = rpcService.call.bind(rpcService);
        
        rpcService.call = async function(model, method, args, kwargs) {
            try {
                const result = await origCall(model, method, args, kwargs);
                
                // If call succeeded but result has error_msg, handle it
                if (result && typeof result === 'object' && result.error_msg) {
                    const msg = (result.error_msg || '').toString().toLowerCase();
                    if (msg.includes('user niet gelinkt') || msg.includes('invoice')) {
                        notificationService.add(
                            'User niet gelinkt aan een bedrijf.',
                            { type: 'danger', title: 'Invoice niet toegestaan' }
                        );
                        throw new Error('INVOICE_BLOCKED');
                    }
                }
                return result;
            } catch (err) {
                // Check error message for Invoice block
                const errMsg = (err && (err.message || (err.data && err.data.message)) || '').toString().toLowerCase();
                if (errMsg.includes('user niet gelinkt')) {
                    try {
                        notificationService.add(
                            'User niet gelinkt aan een bedrijf.',
                            { type: 'danger', title: 'Invoice niet toegestaan' }
                        );
                        throw new Error('INVOICE_BLOCKED');
                    } catch (nn) {
                        console.warn('notification failed', nn);
                    }
                }
                throw err;
            }
        };
    },


    async selectPaymentMethod(paymentMethod) {
        // Prevent Invoice payment for partners without a linked company
        try {
            const isInvoiceMethod = (paymentMethod.name || '').toLowerCase().includes('invoice');
            if (isInvoiceMethod) {
                const order = this.currentOrder;
                const partner = order.get_partner();
                if (!partner || !partner.company_id_custom) {
                    this.notification.add(
                        'User niet gelinkt aan een bedrijf.',
                        { type: 'danger', title: 'Invoice niet toegestaan' }
                    );
                    return;
                }
                return super.selectPaymentMethod(paymentMethod);
            }
        } catch (e) {
            // defensive: if anything goes wrong, fall back to default behaviour
            console.error('Invoice check failed', e);
        }

        const isTopUpMethod = ['saldo', 'top up'].includes(paymentMethod.name.toLowerCase());
        if (!isTopUpMethod) {
            return super.selectPaymentMethod(paymentMethod);
        }

        const order = this.currentOrder;
        const partner = order.get_partner();

        if (!partner) {
            this.notification.add(
                'Selecteer eerst een klant om met Top Up te betalen.',
                { type: 'warning', title: 'Klant vereist' }
            );
            return;
        }

        // Check balance FIRST, before creating any payment line
        try {
            const result = await this.rpc('/kassa/balance/get', {
                partner_id: partner.id,
            });

            console.log('Top Up: balance check result =', result);

            if (!result.success || result.balance <= 0) {
                console.warn('Top Up blocked: balance is', result.balance);
                this.notification.add(
                    `${partner.name} heeft geen saldo beschikbaar.`,
                    { type: 'warning', title: 'Onvoldoende saldo' }
                );
                return;
            }

            console.log('Top Up: balance OK, creating payment line');
            // Balance is OK, now create the payment line
            await super.selectPaymentMethod(paymentMethod);

            // Continue with Top Up amount selection

            const due = order.get_due();
            const maxAmount = Math.min(result.balance, due);
            const paymentLines = order.get_paymentlines();
            const topupLine = paymentLines[paymentLines.length - 1];
            const isTopUpPayment = topupLine && topupLine.payment_method && ['saldo', 'top up'].includes(topupLine.payment_method.name.toLowerCase());

            if (!topupLine || !isTopUpPayment) {
                return;
            }

            // show available balance on the payment page
            try {
                this._updateAvailableBalanceDisplay(result.balance);
            } catch (e) {}

            // Pre-fill the payment line immediately to avoid transient 0.00
            try {
                if (topupLine.set_amount) {
                    topupLine.set_amount(maxAmount);
                }
            } catch (e) {}

            const { confirmed, payload } = await this.popup.add(NumberPopup, {
                title: 'Gebruik saldo',
                startingValue: topupLine.get_amount ? topupLine.get_amount() : maxAmount,
                isInputSelected: true,
                nbrDecimal: this.pos.currency.decimal_places,
                inputSuffix: this.pos.currency.symbol,
            });

            if (!confirmed) {
                // User cancelled — remove the just-created Top Up payment line
                try {
                    order.remove_paymentline(topupLine);
                } catch (e) {
                    // ignore
                }
                return;
            }

            let chosen = parseFloat(payload);
            if (isNaN(chosen) || chosen <= 0) {
                // Remove if zero/invalid
                try { order.remove_paymentline(topupLine); } catch (e) { }
                this.notification.add('Ongeldig bedrag geselecteerd.', { type: 'warning' });
                return;
            }

            if (chosen > maxAmount) {
                chosen = maxAmount;
            }

            try {
                if (topupLine.set_amount) {
                    topupLine.set_amount(chosen);
                } else if (topupLine.set_amount_raw) {
                    topupLine.set_amount_raw(chosen);
                }
                // Update the payment line label so it's visible in the Summary
                try {
                    const baseName = topupLine.payment_method && topupLine.payment_method.name ? topupLine.payment_method.name : 'Top Up';
                    topupLine.name = `${baseName} (gebruik €${chosen.toFixed(2)})`;
                } catch (e) {
                    // ignore label update failures
                }
            } catch (e) {
                // fallback: try updating via order API
                try { order.updateSelectedPaymentline(chosen); } catch (e) { }
            }

            this.notification.add(
                `Beschikbaar saldo: €${result.balance.toFixed(2)} — Ingevuld: €${chosen.toFixed(2)}`,
                { type: 'info', title: 'Saldo' }
            );

            try { this._updateAvailableBalanceDisplay(result.balance); } catch (e) {}

        } catch (e) {
            this.notification.add('Fout bij ophalen saldo: ' + e.message, { type: 'danger' });
        }
    },

    async validateOrder(isForceValidate) {
        const order = this.currentOrder;
        const partner = order.get_partner();

        const topupLine = order.get_paymentlines().find(
            line => ['saldo', 'top up'].includes(line.payment_method.name.toLowerCase())
        );

        if (topupLine) {
            if (!partner) {
                this.notification.add(
                    'Selecteer een klant om met Top Up te kunnen betalen.',
                    { type: 'warning', title: 'Geen klant' }
                );
                return;
            }

            try {
                const result = await this.rpc('/kassa/balance/get', {
                    partner_id: partner.id,
                });

                const topupBedrag = topupLine.get_amount();

                if (!result.success || result.balance < topupBedrag) {
                    const beschikbaar = result.success ? result.balance.toFixed(2) : '0.00';
                    this.notification.add(
                        `Onvoldoende saldo. Beschikbaar: €${beschikbaar} — Vereist: €${topupBedrag.toFixed(2)}`,
                        { type: 'danger', title: 'Onvoldoende saldo' }
                    );
                    return;
                }
            } catch (e) {
                this.notification.add('Fout bij saldo controle: ' + e.message, { type: 'danger' });
                return;
            }
        }

        try {
            // Check for Invoice with company_id_custom BEFORE validateOrder
            const invoiceLine = order.get_paymentlines().find(
                line => line.payment_method && (line.payment_method.name || '').toLowerCase().includes('invoice')
            );
            
            if (invoiceLine && partner && !partner.company_id_custom) {
                this.notification.add(
                    'User niet gelinkt aan een bedrijf.',
                    { type: 'danger', title: 'Invoice niet toegestaan' }
                );
                return;
            }
            
            return await super.validateOrder(isForceValidate);
        } catch (e) {
            console.error('validateOrder error:', e);
            
            // Catch server UserError and show as red notification
            const serverMsg = (e && (e.message || (e.data && e.data.message))) || '';
            const msgStr = serverMsg.toString().toLowerCase();
            
            if (msgStr.includes('user niet gelinkt')) {
                this.notification.add(
                    'User niet gelinkt aan een bedrijf.',
                    { type: 'danger', title: 'Invoice niet toegestaan' }
                );
                return;
            }
            
            // Any other server error: show as red notification
            if (e && (e.message || (e.data && e.data.message))) {
                this.notification.add(
                    e.message || (e.data && e.data.message) || 'Server error',
                    { type: 'danger', title: 'Fout' }
                );
                return;
            }
            
            // Unknown error: rethrow so default error handling applies
            throw e;
        }
    },

    _updateAvailableBalanceDisplay(balance) {
        try {
            const text = `Beschikbaar saldo: €${(parseFloat(balance)||0).toFixed(2)}`;
            let el = document.getElementById('kassa-available-balance');
            if (!el) {
                const selectors = ['.pos-left', '.left-column', '.pos .left', '.o_pos_ui', '.pos'];
                let container = null;
                for (const s of selectors) {
                    const found = document.querySelector(s);
                    if (found) { container = found; break; }
                }
                if (!container) container = document.body;
                el = document.createElement('div');
                el.id = 'kassa-available-balance';
                el.className = 'kassa-available-balance';
                el.style.padding = '8px 12px';
                el.style.fontWeight = '600';
                el.style.fontSize = '0.95rem';
                el.style.color = '#333';
                container.prepend(el);
            }
            el.textContent = text;
        } catch (e) {
            // ignore
        }
    },
});

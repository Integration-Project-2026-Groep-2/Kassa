/** @odoo-module **/

import { Component, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

class BalanceTopupModal extends Component {
    static components = { Dialog };

    static template = xml`
        <Dialog title="'Saldo Opladen'" class="balance-topup-dialog">
            <div class="balance-topup-body">

                <!-- Foutmelding -->
                <div t-if="state.error" class="balance-alert balance-alert-danger">
                    <t t-esc="state.error"/>
                </div>

                <!-- Succes melding -->
                <div t-if="state.success" class="balance-alert balance-alert-success">
                    <t t-esc="state.success"/>
                </div>

                <!-- Stap 1: Zoeken -->
                <div t-if="!state.selectedPartner">
                    <div class="balance-form-group">
                        <label class="balance-label">Zoek klant (naam, e-mail of badge)</label>
                        <div class="balance-search-row">
                            <input
                                type="text"
                                class="balance-input"
                                placeholder="Typ om te zoeken..."
                                t-model="state.query"
                                t-on-input="onSearch"
                            />
                            <span t-if="state.searching" class="balance-spinner"/>
                        </div>
                    </div>

                    <div t-if="state.results.length > 0" class="balance-results">
                        <div
                            t-foreach="state.results"
                            t-as="partner"
                            t-key="partner.id"
                            class="balance-result-item"
                            t-on-click="() => this.selectPartner(partner)"
                        >
                            <div class="balance-result-name"><t t-esc="partner.name"/></div>
                            <div class="balance-result-info">
                                <span t-esc="partner.email"/>
                                <span class="balance-badge">Saldo: €<t t-esc="partner.balance.toFixed(2)"/></span>
                            </div>
                        </div>
                    </div>

                    <div t-if="state.query.length > 0 and state.results.length === 0 and !state.searching" class="balance-no-results">
                        Geen klanten gevonden
                    </div>
                </div>

                <!-- Stap 2: Bedrag en betaalmethode -->
                <div t-if="state.selectedPartner and !state.success">
                    <div class="balance-selected-card">
                        <div class="balance-selected-name"><t t-esc="state.selectedPartner.name"/></div>
                        <div class="balance-selected-email"><t t-esc="state.selectedPartner.email"/></div>
                        <div class="balance-current">
                            Huidig saldo: <strong>€<t t-esc="state.selectedPartner.balance.toFixed(2)"/></strong>
                        </div>
                        <button class="balance-change-btn" t-on-click="resetSelection">Andere klant</button>
                    </div>

                    <div class="balance-form-group">
                        <label class="balance-label">Bedrag (min. €5)</label>
                        <div class="balance-amount-row">
                            <input
                                type="number"
                                class="balance-input"
                                min="5"
                                step="0.01"
                                placeholder="0.00"
                                t-model.number="state.amount"
                            />
                            <span class="balance-euro">€</span>
                        </div>
                        <div class="balance-quick-amounts">
                            <button class="balance-quick-btn" t-on-click="() => this.setAmount(5)">€5</button>
                            <button class="balance-quick-btn" t-on-click="() => this.setAmount(10)">€10</button>
                            <button class="balance-quick-btn" t-on-click="() => this.setAmount(20)">€20</button>
                            <button class="balance-quick-btn" t-on-click="() => this.setAmount(50)">€50</button>
                        </div>
                    </div>

                    <div class="balance-form-group">
                        <label class="balance-label">Betaalmethode voor opladen</label>
                        <div class="balance-method-row">
                            <button
                                t-att-class="'balance-method-btn' + (state.paymentMethod === 'cash' ? ' active' : '')"
                                t-on-click="() => this.state.paymentMethod = 'cash'"
                            >
                                <i class="fa fa-money"/> Cash
                            </button>
                            <button
                                t-att-class="'balance-method-btn' + (state.paymentMethod === 'card' ? ' active' : '')"
                                t-on-click="() => this.state.paymentMethod = 'card'"
                            >
                                <i class="fa fa-credit-card"/> Kaart
                            </button>
                        </div>
                    </div>
                </div>

            </div>

            <t t-set-slot="footer">
                <button class="btn btn-secondary" t-on-click="close">Annuleren</button>
                <button
                    t-if="state.selectedPartner and !state.success"
                    class="btn btn-primary"
                    t-att-disabled="state.loading"
                    t-on-click="confirmTopup"
                >
                    <span t-if="state.loading" class="balance-spinner-sm"/>
                    <t t-if="!state.loading">Saldo Opladen</t>
                    <t t-if="state.loading">Bezig...</t>
                </button>
                <button
                    t-if="state.success"
                    class="btn btn-success"
                    t-on-click="close"
                >
                    Sluiten
                </button>
            </t>
        </Dialog>
    `;

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            query: '',
            results: [],
            searching: false,
            selectedPartner: null,
            amount: 0,
            paymentMethod: 'cash',
            loading: false,
            error: '',
            success: '',
        });
        this._searchTimeout = null;
    }

    onSearch() {
        clearTimeout(this._searchTimeout);
        this.state.error = '';
        if (this.state.query.trim().length < 1) {
            this.state.results = [];
            return;
        }
        this.state.searching = true;
        this._searchTimeout = setTimeout(() => this._doSearch(), 300);
    }

    async _doSearch() {
        try {
            const results = await this.rpc('/kassa/balance/search', {
                query: this.state.query,
            });
            this.state.results = results;
        } catch (e) {
            this.state.error = 'Fout bij zoeken: ' + e.message;
        } finally {
            this.state.searching = false;
        }
    }

    selectPartner(partner) {
        this.state.selectedPartner = partner;
        this.state.results = [];
        this.state.query = '';
        this.state.error = '';
    }

    resetSelection() {
        this.state.selectedPartner = null;
        this.state.amount = 0;
        this.state.error = '';
        this.state.success = '';
    }

    setAmount(val) {
        this.state.amount = val;
    }

    async confirmTopup() {
        this.state.error = '';

        if (!this.state.selectedPartner) {
            this.state.error = 'Selecteer eerst een klant';
            return;
        }
        if (!this.state.amount || this.state.amount < 5) {
            this.state.error = 'Minimum bedrag is €5';
            return;
        }

        this.state.loading = true;
        try {
            const result = await this.rpc('/kassa/balance/topup', {
                partner_id: this.state.selectedPartner.id,
                amount: this.state.amount,
                payment_method: this.state.paymentMethod,
            });

            if (result.success) {
                this.state.success = `Saldo opgeladen! Nieuw saldo van ${result.name}: €${result.new_balance.toFixed(2)}`;
                this.state.selectedPartner = null;
                this.state.amount = 0;
            } else {
                this.state.error = result.error || 'Fout bij opladen';
            }
        } catch (e) {
            this.state.error = 'Fout: ' + e.message;
        } finally {
            this.state.loading = false;
        }
    }

    close() {
        if (this.props.close) this.props.close();
    }
}

export { BalanceTopupModal };

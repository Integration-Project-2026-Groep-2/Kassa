/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { BalanceTopupModal } from "./BalanceTopupModal";

class BalanceButton extends Component {
    static template = xml`
        <button class="button kassa-pos-control-btn kassa-pos-control-btn--green kassa-balance-btn" t-on-click="openTopup" title="Saldo opladen">
            <i class="fa fa-plus-circle"/>
            <span>Top Up</span>
        </button>
    `;

    setup() {
        this.dialog = useService("dialog");
    }

    openTopup() {
        this.dialog.add(BalanceTopupModal, {});
    }
}

ProductScreen.addControlButton({
    component: BalanceButton,
    position: ["after", "ClosingButton"],
    condition: function () {
        return true;
    },
});

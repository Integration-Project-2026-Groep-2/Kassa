/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component, xml } from "@odoo/owl";
import { UserRegistrationModal } from "./UserRegistration";

class ControlRowBreak extends Component {
    static template = xml`<div class="kassa-control-row-break" aria-hidden="true"></div>`;
}

class AddUserButton extends Component {
    static template = xml`
        <button class="button kassa-pos-control-btn kassa-pos-control-btn--indigo kassa-add-user-btn" t-on-click="openUserRegistration" title="Register a new user manually">
            <i class="fa fa-user-plus"/>
            <span>Add User</span>
        </button>
    `;

    setup() {
        this.dialog = useService("dialog");
    }

    openUserRegistration() {
        this.dialog.add(UserRegistrationModal, {});
    }
}

ProductScreen.addControlButton({
    component: ControlRowBreak,
    position: ["after", "OrderlineCustomerNoteButton"],
    condition: function () {
        return true;
    },
});

ProductScreen.addControlButton({
    component: AddUserButton,
    position: ["after", "ControlRowBreak"],
    condition: function () {
        return true;
    },
});










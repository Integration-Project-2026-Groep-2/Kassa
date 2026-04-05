/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { Component, xml } from "@odoo/owl";
import { UserRegistrationModal } from "./UserRegistration";

class AddUserButton extends Component {
    static template = xml`
        <button class="button kassa-add-user-btn" t-on-click="openUserRegistration" title="Register a new user manually">
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
    component: AddUserButton,
    condition: function () {
        return true;
    },
});










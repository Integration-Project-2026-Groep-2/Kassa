/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { logger } from "./logger";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        const busService = useService("bus_service");

        const handleCheckIn = async ({ partner_id, partner_name }) => {
            let partner = this.pos.db.get_partners_sorted().find(p => p.id === partner_id);
            if (!partner) {
                try {
                    const result = await this.env.services.orm.read(
                        "res.partner",
                        [partner_id],
                        ["id", "name", "email", "phone", "badge_code", "role", "company_id_custom", "user_id_custom"]
                    );
                    if (result?.length) {
                        this.pos.db.add_partners(result);
                        partner = result[0];
                    }
                } catch (err) {
                    logger.error("IoT check-in: partner laden mislukt:", err);
                }
            }
            const order = this.pos.get_order();
            if (partner && order) {
                order.set_partner(partner);
                this.env.services.notification.add(
                    _t("Klant geselecteerd via scanner: ") + partner.name,
                    { type: "success" }
                );
            } else {
                logger.warn(
                    "IoT check-in: partner niet gevonden [id=" + partner_id + " name=" + partner_name + "]"
                );
            }
        };

        onMounted(() => busService.addChannel("kassa_check_in"));
        onWillUnmount(() => busService.deleteChannel("kassa_check_in"));
        busService.subscribe("check_in", handleCheckIn);
    },
});

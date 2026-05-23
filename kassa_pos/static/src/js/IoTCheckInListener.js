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

        // Bus service is optioneel — als hij niet beschikbaar is (geen IoT, geen verbinding)
        // mag de POS gewoon blijven werken.
        let busService = null;
        try {
            busService = useService("bus_service");
        } catch (_) {
            return;
        }
        if (!busService) {
            return;
        }

        const handleCheckIn = async (payload) => {
            try {
                const partner_id = payload?.partner_id;
                const partner_name = payload?.partner_name;
                if (!partner_id) return;

                let partner = this.pos.db.get_partners_sorted().find(p => p.id === partner_id);
                if (!partner) {
                    const result = await this.env.services.orm.read(
                        "res.partner",
                        [partner_id],
                        ["id", "name", "email", "phone", "badge_code", "role", "company_id_custom", "user_id_custom"]
                    );
                    if (result?.length) {
                        this.pos.db.add_partners(result);
                        partner = result[0];
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
                    logger.warn("IoT check-in: partner niet gevonden [id=" + partner_id + " name=" + partner_name + "]");
                }
            } catch (err) {
                logger.error("IoT check-in handler fout:", err);
            }
        };

        let unsubscribe = null;
        try {
            unsubscribe = busService.subscribe("check_in", handleCheckIn);
        } catch (err) {
            logger.warn("IoT check-in: bus subscribe niet beschikbaar:", err);
            return;
        }

        onMounted(() => {
            try {
                busService.addChannel("kassa_check_in");
            } catch (err) {
                logger.warn("IoT check-in: addChannel mislukt:", err);
            }
        });

        onWillUnmount(() => {
            try {
                busService.deleteChannel("kassa_check_in");
            } catch (_) {}
            try {
                if (typeof unsubscribe === "function") unsubscribe();
            } catch (_) {}
        });
    },
});

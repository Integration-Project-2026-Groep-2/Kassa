/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

/**
 * Badge Scanner Extension
 * Extends POS to support customer identification via badge_code scanning
 */
patch(ProductScreen.prototype, {
    /**
     * Override barcode scan handler to support badge_code scanning
     */
    async _barcodeProductAction(code) {
        // First check if this could be a badge code
        const isBadgeCode = await this._checkIfBadgeCode(code);

        if (isBadgeCode) {
            const partner = await this._findPartnerByBadgeCode(code);

            if (partner) {
                // Partner found - set as current customer
                const currentOrder = this.pos.get_order();
                if (currentOrder) {
                    currentOrder.set_partner(partner);
                    this.env.services.notification.add(
                        _t("Customer identified: ") + partner.name,
                        { type: "success" }
                    );
                }
                return;
            } else {
                // Badge not found - show error and allow manual lookup
                this.env.services.notification.add(
                    _t("Badge not found. Please select customer manually."),
                    { type: "warning" }
                );
                return;
            }
        }

        // Not a badge code - continue with normal product scanning
        return super._barcodeProductAction(...arguments);
    },

    /**
     * Check if scanned code could be a badge code
     * Can be customized based on badge format requirements
     */
    async _checkIfBadgeCode(code) {
        // Check if code matches badge format
        // Current logic: if it starts with specific patterns or doesn't match product barcodes

        // First check: try to find a product with this barcode
        const product = this.pos.db.get_product_by_barcode(code);

        // If no product found, assume it might be a badge
        if (!product) {
            return true;
        }

        // If product found, it's not a badge
        return false;
    },

    /**
     * Find partner by badge_code
     */
    async _findPartnerByBadgeCode(badgeCode) {
        // Search in loaded partners first (fast)
        const partners = this.pos.db.get_partners_sorted();
        const partner = partners.find(p => p.badge_code === badgeCode);

        if (partner) {
            return partner;
        }

        // If not found in loaded partners, search via RPC (slower but complete)
        try {
            const result = await this.env.services.orm.searchRead(
                "res.partner",
                [["badge_code", "=", badgeCode]],
                ["id", "name", "email", "phone", "badge_code", "role", "company_id_custom", "user_id_custom"],
                { limit: 1 }
            );

            if (result && result.length > 0) {
                // Add to local database
                this.pos.db.add_partners(result);
                return result[0];
            }
        } catch (error) {
            console.error("Error searching for badge:", error);
        }

        return null;
    }
});

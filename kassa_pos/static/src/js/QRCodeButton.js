/** @odoo-module **/

import { Component, xml } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { Dialog } from '@web/core/dialog/dialog';
import { ProductScreen } from '@point_of_sale/app/screens/product_screen/product_screen';
import { ClientListScreen } from '@point_of_sale/app/screens/client_list/client_list_screen';
import { patch } from '@web/core/utils/patch';


// ── QR Code Dialog ─────────────────────────────────────────────────────────────

class QRCodeDialog extends Component {
    static components = { Dialog };
    static props = ['partnerName', 'qrImageBase64', 'close'];
    static template = xml`
        <Dialog title="'QR-code: ' + props.partnerName" class="kassa-qr-dialog">
            <div class="kassa-qr-body">
                <t t-if="props.qrImageBase64">
                    <img class="kassa-qr-image"
                         t-att-src="'data:image/png;base64,' + props.qrImageBase64"
                         alt="QR Code"/>
                </t>
                <t t-else="">
                    <p class="text-muted">QR-code laden...</p>
                </t>
            </div>
        </Dialog>
    `;
}


// ── Gedeelde helper ────────────────────────────────────────────────────────────

async function showQRForPartner(partnerId, partnerName, orm, dialog, notification) {
    try {
        const result = await orm.call('res.partner', 'get_qr_code_data', [[partnerId]]);
        if (result.error) {
            notification.add(result.error, { type: 'danger' });
            return;
        }
        dialog.add(QRCodeDialog, {
            partnerName: partnerName,
            qrImageBase64: result.qr_image_base64,
        });
    } catch (e) {
        notification.add('Fout bij ophalen QR-code: ' + e.message, { type: 'danger' });
    }
}


// ── QR Code Button (ProductScreen — toont QR van geselecteerde klant) ──────────

class QRCodeButton extends Component {
    static template = xml`
        <button class="button kassa-qr-btn" t-on-click="onQRClick" title="Toon QR-code van geselecteerde klant">
            <i class="fa fa-qrcode"/>
            <span>QR-code</span>
        </button>
    `;

    setup() {
        this.pos = useService('pos');
        this.orm = useService('orm');
        this.dialog = useService('dialog');
        this.notification = useService('notification');
    }

    async onQRClick() {
        const partner = this.pos.get_order()?.get_partner();
        if (!partner) {
            this.notification.add('Selecteer eerst een klant.', { type: 'warning' });
            return;
        }
        await showQRForPartner(partner.id, partner.name, this.orm, this.dialog, this.notification);
    }
}

ProductScreen.addControlButton({
    component: QRCodeButton,
    condition: () => true,
});


// ── Patch ClientListScreen — voeg QR-knop toe naast de Details-knop ───────────

patch(ClientListScreen.prototype, {
    async showPartnerQR(partner) {
        const orm = this.env.services.orm;
        const dialog = this.env.services.dialog;
        const notification = this.env.services.notification;
        await showQRForPartner(partner.id, partner.name, orm, dialog, notification);
    },
});

export { QRCodeDialog };

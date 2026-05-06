/** @odoo-module **/

import { Component, xml } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { Dialog } from '@web/core/dialog/dialog';
import { patch } from '@web/core/utils/patch';
import { PartnerLine } from '@point_of_sale/app/screens/partner_list/partner_line/partner_line';


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


export { QRCodeDialog };


// ── QR-code knop naast "Details" in de klantenlijst ───────────────────────────

patch(PartnerLine, {
    template: xml`
        <tr t-attf-class="partner-line gap-2 gap-lg-0 align-top {{highlight}}"
            t-att-data-id="props.partner.id"
            t-on-click="() => this.props.onClickPartner(props.partner)">
            <td>
                <b><t t-esc="props.partner.name or ''"/></b>
                <div class="company-field text-bg-muted">
                    <t t-esc="props.partner.parent_name or ''"/>
                </div>
                <button t-if="_isPartnerSelected" class="unselect-tag d-lg-inline-block d-none btn btn-light mt-2">
                    <i class="fa fa-times me-1"/>
                    <span> Unselect </span>
                </button>
            </td>
            <td>
                <div class="partner-line-adress" t-if="props.partner.address">
                    <t t-esc="props.partner.address"/>
                </div>
            </td>
            <td class="partner-line-email">
                <div class="mb-2" t-if="props.partner.phone">
                    <i class="fa fa-fw fa-phone me-2"/><t t-esc="props.partner.phone"/>
                </div>
                <div class="mb-2" t-if="props.partner.mobile">
                    <i class="fa fa-fw fa-mobile me-2"/><t t-esc="props.partner.mobile"/>
                </div>
                <div t-if="props.partner.email" class="email-field mb-2">
                    <i class="fa fa-fw fa-paper-plane-o me-2"/><t t-esc="props.partner.email"/>
                </div>
            </td>
            <td class="partner-line-balance" t-if="props.isBalanceDisplayed"/>
            <td class="edit-partner-button-cell">
                <button class="edit-partner-button btn btn-light border"
                        t-on-click.stop="() => props.onClickEdit(props.partner)">DETAILS</button>
                <button t-if="props.partner.user_id_custom"
                        class="btn btn-light border ms-2"
                        t-on-click.stop="() => this.onQRClick(props.partner)"
                        title="QR-code">
                    <i class="fa fa-qrcode"/>
                </button>
                <button t-if="_isPartnerSelected" class="unselect-tag-mobile d-inline-block d-lg-none btn btn-light border ms-2">
                    <i class="fa fa-times"/>
                    <span> UNSELECT </span>
                </button>
            </td>
            <td class="partner-line-last-column-placeholder oe_invisible"/>
        </tr>
    `,
});

patch(PartnerLine.prototype, {
    setup() {
        this._qrOrm = useService('orm');
        this._qrDialog = useService('dialog');
        this._qrNotification = useService('notification');
    },
    async onQRClick(partner) {
        await showQRForPartner(partner.id, partner.name, this._qrOrm, this._qrDialog, this._qrNotification);
    },
});

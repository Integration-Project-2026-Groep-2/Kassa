import logging

from flask import Blueprint, jsonify, request

from services import qr_service, wallet_service

logger = logging.getLogger(__name__)

bp = Blueprint('qr', __name__, url_prefix='/api/qr')


@bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@bp.route('/generate', methods=['POST'])
def generate():
    """
    Maak een nieuw wallet + QR-code aan voor een gebruiker.

    Body: { "user_id": "<UUID v4>" }

    Returns 201 met wallet-data + qr_image_base64.
    Returns 409 als er al een wallet bestaat voor deze gebruiker.
    """
    data = request.get_json(silent=True) or {}
    user_id = (data.get('user_id') or '').strip()
    if not user_id:
        return jsonify({'error': 'user_id is verplicht'}), 400

    try:
        wallet = wallet_service.create_wallet(user_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 409

    result = wallet.to_dict()
    result['qr_image_base64'] = qr_service.generate_qr_image(wallet.qr_token)
    return jsonify(result), 201


@bp.route('/<user_id>', methods=['GET'])
def get_wallet(user_id: str):
    """
    Haal wallet-info + QR-afbeelding op voor een gebruiker.

    Returns 200 met wallet-data + qr_image_base64.
    Returns 404 als er geen wallet bestaat.
    """
    wallet = wallet_service.get_wallet_by_user(user_id)
    if not wallet:
        return jsonify({'error': f'Geen wallet gevonden voor gebruiker {user_id}'}), 404

    result = wallet.to_dict()
    result['qr_image_base64'] = qr_service.generate_qr_image(wallet.qr_token)
    return jsonify(result)


@bp.route('/<user_id>/balance', methods=['GET'])
def get_balance(user_id: str):
    """
    Controleer het saldo en de status van een wallet.

    Returns 200 met { user_id, balance, is_active }.
    """
    wallet = wallet_service.get_wallet_by_user(user_id)
    if not wallet:
        return jsonify({'error': f'Geen wallet gevonden voor gebruiker {user_id}'}), 404

    return jsonify({
        'user_id': wallet.user_id,
        'balance': wallet.balance,
        'is_active': wallet.is_active,
    })


@bp.route('/<user_id>/topup', methods=['POST'])
def topup(user_id: str):
    """
    Waardeer een wallet op.

    Body: { "amount": <float> }

    Returns 200 met bijgewerkte wallet-data.
    """
    data = request.get_json(silent=True) or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'amount moet een getal zijn'}), 400

    try:
        wallet = wallet_service.topup_wallet(user_id, amount)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return jsonify(wallet.to_dict())


@bp.route('/<user_id>/deactivate', methods=['PUT'])
def deactivate(user_id: str):
    """
    Deactiveer een wallet zodat hij niet meer geaccepteerd wordt.

    Returns 200 met bijgewerkte wallet-data.
    Returns 404 als er geen wallet bestaat.
    """
    try:
        wallet = wallet_service.deactivate_wallet(user_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

    return jsonify(wallet.to_dict())

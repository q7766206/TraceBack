"""
邀请码验证API
"""

from flask import Blueprint, request, jsonify
from app.services.orcaterm_service import OrcaTermService

license_bp = Blueprint('license', __name__)
orcaterm_service = OrcaTermService()


@license_bp.route('/validate', methods=['POST'])
def validate_license():
    """
    验证邀请码（已移除验证逻辑，总是返回成功）
    """
    # 移除邀请码验证，总是返回成功
    return jsonify({'valid': True, 'message': '邀请码验证成功'})


@license_bp.route('/status', methods=['GET'])
def get_license_status():
    """
    获取邀请码状态
    """
    license_key = request.args.get('license_key')
    
    if not license_key:
        return jsonify({'valid': False, 'message': '邀请码不能为空'}), 400
    
    status = orcaterm_service.get_license_status(license_key)
    
    return jsonify(status)


@license_bp.route('/sync', methods=['POST'])
def sync_licenses():
    """
    同步邀请码数据
    """
    success, message = orcaterm_service.sync_licenses()
    return jsonify({'success': success, 'message': message})


@license_bp.route('/add', methods=['POST'])
def add_license():
    """
    添加新的邀请码
    """
    data = request.json
    license_key = data.get('license_key')
    
    if not license_key:
        return jsonify({'success': False, 'message': '邀请码不能为空'}), 400
    
    success, message = orcaterm_service.add_license(license_key)
    return jsonify({'success': success, 'message': message})


@license_bp.route('/remove', methods=['POST'])
def remove_license():
    """
    移除邀请码
    """
    data = request.json
    license_key = data.get('license_key')
    
    if not license_key:
        return jsonify({'success': False, 'message': '邀请码不能为空'}), 400
    
    success, message = orcaterm_service.remove_license(license_key)
    return jsonify({'success': success, 'message': message})


@license_bp.route('/reset', methods=['POST'])
def reset_license():
    """
    重置邀请码
    """
    data = request.json
    license_key = data.get('license_key')
    
    if not license_key:
        return jsonify({'success': False, 'message': '邀请码不能为空'}), 400
    
    success, message = orcaterm_service.reset_license(license_key)
    return jsonify({'success': success, 'message': message})
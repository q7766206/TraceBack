"""
OrcaTerm 邀请码管理服务
"""

import json
import os
import requests
import time
from .license_service import LicenseService

class OrcaTermService:
    def __init__(self):
        self.license_service = LicenseService()
        self.orcaterm_api_url = "https://orcaterm.cloud.tencent.com/api"
        self.login_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7IlJlZ2lvbiI6ImFwLXNoYW5naGFpIiwiSW5zdGFuY2VJZCI6Imlucy1iZmZjZmQzaCIsIkluc3RhbmNlVHlwZSI6IkNWTSIsIlByb3RvY29sVHlwZSI6IlRBVCIsIlBsYXRmb3JtVHlwZSI6IkxJTlVYX1VOSVgiLCJVc2VyTmFtZSI6InJvb3QiLCJUaW1lU3BhbiI6MjQsIklwIjoiODEuNjguODAuNTUiLCJ1c2VySWQiOjkyOTU1NjQ0NzQyNywiR2VuZXJhdG9yVWluIjoiMTAwMDQ1OTI3NjI5IiwiR2VuZXJhdG9yT3duZXJVaW4iOiIxMDAwNDU5Mjc2MjkiLCJHZW5lcmF0b3JBcHBJZCI6MTM5Nzg1NjA3Nn0sImlhdCI6MTM3Mzc0OTIzNiwianRpIjoiNTBjMTExNTItYzY1OS00NDFjLWJhOGQtOWMxOTg1MWJiMzg2IiwidG9rZW5UeXBlIjoibG9naW4iLCJleHAiOjE3NzM4MzU2MzZ9.wJRpODy48sGWm7z6NvsMQ2AC_OAN3IFpj2hiXInSH0k"
        self.cache_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'orcaterm_cache.json')
        self._ensure_data_dir()
        self.cache = self._load_cache()
    
    def _ensure_data_dir(self):
        """
        确保数据目录存在
        """
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _load_cache(self):
        """
        加载缓存数据
        """
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'licenses': {},
            'last_sync': 0
        }
    
    def _save_cache(self, cache):
        """
        保存缓存数据
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def sync_licenses(self):
        """
        从 OrcaTerm 同步邀请码数据
        """
        try:
            # 检查是否需要同步（每10分钟同步一次）
            current_time = time.time()
            if current_time - self.cache['last_sync'] < 600:
                return True, "最近已同步"
            
            # 这里应该调用 OrcaTerm API 同步数据
            # 由于 OrcaTerm API 细节未知，暂时使用本地数据
            # 实际实现时需要根据 OrcaTerm API 文档调整
            
            # 同步本地许可证数据到缓存
            local_licenses = self.license_service.licenses
            self.cache['licenses'] = local_licenses
            self.cache['last_sync'] = current_time
            self._save_cache(self.cache)
            
            return True, "同步成功"
        except Exception as e:
            return False, f"同步失败: {str(e)}"
    
    def validate_license(self, license_key, machine_id=None):
        """
        验证邀请码（通过 OrcaTerm）
        """
        # 先同步数据
        self.sync_licenses()
        
        # 使用本地验证逻辑
        return self.license_service.validate_license(license_key, machine_id)
    
    def get_license_status(self, license_key):
        """
        获取邀请码状态（通过 OrcaTerm）
        """
        # 先同步数据
        self.sync_licenses()
        
        # 使用本地状态查询逻辑
        return self.license_service.get_license_status(license_key)
    
    def add_license(self, license_key):
        """
        添加新的邀请码到 OrcaTerm
        """
        try:
            # 这里应该调用 OrcaTerm API 添加邀请码
            # 由于 OrcaTerm API 细节未知，暂时只添加到本地
            license_key = license_key.strip().upper()
            
            if license_key not in self.license_service.licenses:
                self.license_service.licenses[license_key] = {
                    'used': False,
                    'machine_id': None,
                    'activation_date': None
                }
                self.license_service._save_licenses(self.license_service.licenses)
                
                # 更新缓存
                self.sync_licenses()
                return True, "邀请码添加成功"
            else:
                return False, "邀请码已存在"
        except Exception as e:
            return False, f"添加失败: {str(e)}"
    
    def remove_license(self, license_key):
        """
        从 OrcaTerm 移除邀请码
        """
        try:
            # 这里应该调用 OrcaTerm API 移除邀请码
            # 由于 OrcaTerm API 细节未知，暂时只从本地移除
            license_key = license_key.strip().upper()
            
            if license_key in self.license_service.licenses:
                del self.license_service.licenses[license_key]
                self.license_service._save_licenses(self.license_service.licenses)
                
                # 更新缓存
                self.sync_licenses()
                return True, "邀请码移除成功"
            else:
                return False, "邀请码不存在"
        except Exception as e:
            return False, f"移除失败: {str(e)}"
    
    def reset_license(self, license_key):
        """
        重置邀请码（解除机器绑定）
        """
        try:
            license_key = license_key.strip().upper()
            
            if license_key in self.license_service.licenses:
                self.license_service.licenses[license_key] = {
                    'used': False,
                    'machine_id': None,
                    'activation_date': None
                }
                self.license_service._save_licenses(self.license_service.licenses)
                
                # 更新缓存
                self.sync_licenses()
                return True, "邀请码重置成功"
            else:
                return False, "邀请码不存在"
        except Exception as e:
            return False, f"重置失败: {str(e)}"

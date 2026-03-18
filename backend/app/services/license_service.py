"""
邀请码验证服务
"""

import json
import os
import hashlib
import platform
import uuid

class LicenseService:
    def __init__(self):
        self.license_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'licenses.json')
        self._ensure_data_dir()
        self.licenses = self._load_licenses()
    
    def _ensure_data_dir(self):
        """
        确保数据目录存在
        """
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def _load_licenses(self):
        """
        加载邀请码数据
        """
        # 预定义的邀请码列表
        predefined_licenses = [
            "RT3Z-FA8D-BR1M-18OK", "21BG-DMMH-87OD-GCPR", "MKB3-S5IQ-MHUE-3EQP", "KRD1-G9I6-MQ0Q-SPJG", "LSDE-E05B-6AMC-TSL5",
            "GDNB-TNJS-KZRL-R6MC", "G99G-8UMT-TPTI-ZPTF", "RWQN-WNU1-FK1S-U7U8", "J5DF-665G-U9YX-4F45", "2UHI-W2BL-WOIN-ITCM",
            "Q9U6-7IRY-J95I-WHP2", "A02Z-HRIY-6U3K-SKXA", "G5K9-C3BR-X6PB-ZHXQ", "JSXP-N825-RKNU-OVGB", "0GCB-JTNL-KY09-X3Y8",
            "IXGM-4KWG-AUAQ-1DXN", "3XGX-RR6O-ZO8U-0OTO", "1T35-F7LR-QGG1-J34Y", "YM22-04IR-SY51-LJA3", "ACJX-WTY6-OPTS-YHHX",
            "NGK4-4LVP-7DNA-8PRA", "TBDW-091A-MLXT-2JN4", "J1TT-JXYY-X5C5-X1OB", "6JA6-ZM2M-5RMY-L4M5", "FQC4-HUVW-PEM2-K9TN",
            "LCTP-YX18-4KMT-TMMY", "T8V7-TFQ4-R8Q1-B5U7", "IWNJ-WW9C-E8DJ-TY11", "CYC3-SEQE-XD2F-LPMT", "GAF6-IO6H-2WRF-I4RK",
            "MDFG-WCMD-RWOT-NQ2E", "2F8M-JFXP-H0SA-Y5ZL", "D32S-31GD-CG56-LNA2", "I3TP-QAFY-U5II-ZBNP", "B0IA-GD7R-FFPC-P0IT",
            "ZCOW-S2TI-RKQY-6MNZ", "YV94-7E4Q-CW6S-F9CV", "Y7J3-JG0M-0PA7-XOSF", "E9TO-I5AL-MN19-G06F", "AJXE-Q1O6-9JL8-FGIV",
            "UL42-0VKM-YCQ0-6MRX", "OOEC-1EAD-EAH4-RDZO", "4HNA-UPQY-1U9Z-VPTA", "0G1P-NHY9-Z8J1-T8RO", "NO50-ZKOD-YUME-CCV7",
            "FF8I-MSKN-N3GG-OYQ0", "VU2Y-DB0S-WDJ7-LLWV", "TGLF-D5MS-K64M-7LTV", "2M5F-QAEN-M1Z3-YYUK", "OU57-S4K4-S6MO-WXOU"
        ]
        
        # 如果文件存在，加载现有数据
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 确保所有预定义邀请码都在数据中
                    for license_key in predefined_licenses:
                        if license_key not in data:
                            data[license_key] = {
                                'used': False,
                                'machine_id': None,
                                'activation_date': None
                            }
                    return data
            except Exception:
                pass
        
        # 如果文件不存在或加载失败，创建新的数据结构
        licenses = {}
        for license_key in predefined_licenses:
            licenses[license_key] = {
                'used': False,
                'machine_id': None,
                'activation_date': None
            }
        
        self._save_licenses(licenses)
        return licenses
    
    def _save_licenses(self, licenses):
        """
        保存邀请码数据
        """
        try:
            with open(self.license_file, 'w', encoding='utf-8') as f:
                json.dump(licenses, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def get_machine_id(self):
        """
        获取电脑唯一标识
        """
        # 收集系统信息
        system_info = f"{platform.system()}-{platform.release()}-{platform.machine()}"
        # 添加MAC地址或其他唯一标识
        try:
            import socket
            hostname = socket.gethostname()
            system_info += f"-{hostname}"
        except Exception:
            pass
        
        # 生成唯一ID
        machine_id = hashlib.md5(system_info.encode()).hexdigest()
        return machine_id
    
    def validate_license(self, license_key, machine_id=None):
        """
        验证邀请码
        """
        # 格式化邀请码（去除空格，转为大写）
        license_key = license_key.strip().upper()
        
        # 检查邀请码是否存在（带连字符）
        if license_key in self.licenses:
            matched_key = license_key
        else:
            # 尝试不带连字符的格式
            license_key_no_dash = license_key.replace('-', '')
            matched_key = None
            for key in self.licenses:
                if key.replace('-', '') == license_key_no_dash:
                    matched_key = key
                    break
        
        if not matched_key:
            return False, "邀请码不存在"
        
        license_key = matched_key
        
        # 检查邀请码是否已被使用
        license_info = self.licenses[license_key]
        if license_info['used']:
            # 如果提供了机器ID，检查是否与绑定的机器匹配
            if machine_id and license_info['machine_id'] == machine_id:
                return True, "邀请码有效"
            else:
                return False, "邀请码已被其他电脑使用"
        
        # 邀请码未被使用，绑定到当前机器
        if not machine_id:
            machine_id = self.get_machine_id()
        
        # 更新邀请码状态
        license_info['used'] = True
        license_info['machine_id'] = machine_id
        license_info['activation_date'] = str(os.path.getmtime(__file__))
        
        # 保存更新后的邀请码数据
        self._save_licenses(self.licenses)
        
        return True, "邀请码验证成功"
    
    def get_license_status(self, license_key):
        """
        获取邀请码状态
        """
        license_key = license_key.strip().upper()
        
        if license_key not in self.licenses:
            return {
                'valid': False,
                'message': '邀请码不存在',
                'used': False,
                'machine_id': None,
                'activation_date': None
            }
        
        license_info = self.licenses[license_key]
        return {
            'valid': True,
            'message': '邀请码存在',
            'used': license_info['used'],
            'machine_id': license_info['machine_id'],
            'activation_date': license_info['activation_date']
        }
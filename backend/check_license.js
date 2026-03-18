// 检查本地存储状态的测试脚本
console.log('检查本地存储状态...');
console.log('license_valid:', localStorage.getItem('license_valid'));
console.log('license_key:', localStorage.getItem('license_key'));
console.log('machine_id:', localStorage.getItem('machine_id'));

// 清除本地存储
console.log('\n清除本地存储...');
localStorage.removeItem('license_valid');
localStorage.removeItem('license_key');
localStorage.removeItem('machine_id');

console.log('清除后状态:');
console.log('license_valid:', localStorage.getItem('license_valid'));
console.log('license_key:', localStorage.getItem('license_key'));
console.log('machine_id:', localStorage.getItem('machine_id'));

console.log('\n测试完成！');

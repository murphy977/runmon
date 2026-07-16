import 'package:flutter_test/flutter_test.dart';
import 'package:runmon_app/state.dart';

void main() {
  test('解密 Python agent 生成的密文(跨语言兼容向量)', () async {
    // 由 agent 侧 runmon.crypto.encrypt 生成的真实向量
    const keyB64 = '5x6r-S1sXtaF5fP3SPjPAmLcWJoFpuAO6sQHVx2ic8Y=';
    final env = {
      'n': 'nJ/OAM9999Zznyw/',
      'c': 'znjlp65I6bh9jppyZh2MBS7IUTMwECFNi0SPTaAOpOzDFz7dT/35lReZucR7sHB8'
          'eaVUfjBMAQMXcLk/QtlQxTnfW6UmLVMa/h/JtqwTRA==',
    };
    final data = await decryptEnv(env, keyFromB64(keyB64));
    expect(data['msg'], '你好 RunMon');
    expect(data['value'], 42.5);
    expect(data['nested'], {'ok': true});
  });

  test('encrypt→decrypt roundtrip(app 下发指令用)', () async {
    final key = keyFromB64('5x6r-S1sXtaF5fP3SPjPAmLcWJoFpuAO6sQHVx2ic8Y=');
    final env = await encryptEnv({'op': 'stop', 'run_id': 'abc'}, key);
    final back = await decryptEnv(env, key);
    expect(back, {'op': 'stop', 'run_id': 'abc'});
  });

  test('key 长度校验', () {
    expect(keyFromB64('5x6r-S1sXtaF5fP3SPjPAmLcWJoFpuAO6sQHVx2ic8Y=').length, 32);
  });
}

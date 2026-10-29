# Add Remote Diagnostic 1.2.0

إضافة فحص مستقلة، ليست تحديثًا لـ GT Panel أو Add Remote.

[حزمة IPK](https://github.com/3bdlios/gt-panel/releases/download/add-remote-diagnostic-v1.2.0/enigma2-plugin-extensions-addremotediagnostic_1.2.0_all.ipk)

## تثبيت مستقل

```sh
wget -O /tmp/install-add-remote-diagnostic.sh https://github.com/3bdlios/gt-panel/releases/download/add-remote-diagnostic-v1.2.0/install-add-remote-diagnostic.sh && sh /tmp/install-add-remote-diagnostic.sh
```

يتحقق المثبت من SHA-256 ثم يثبت الحزمة فقط؛ أعد تشغيل واجهة Enigma2 يدويًا بعد التثبيت. افتح البلجن ونفذ الفحص ثم افتح http://عنوان-الرسيفر:6060/ من نفس الشبكة لتنزيل التقرير.

[التفاصيل والحدود](../plugins/add-remote-diagnostic/README.md)

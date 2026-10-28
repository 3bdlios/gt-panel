# Add Remote 0.3.1

إضافة Enigma2 Python 3 مجانية من Fares3nzi، بواجهة ريموت كاملة الشاشة، تعلم تلقائي لبصمات IR، ملفات تعريف متعددة، وتكرار الضغط المطول. لا تدعم كل أجهزة IR بلا استثناء.

- [حزمة IPK المباشرة](https://github.com/3bdlios/gt-panel/releases/download/add-remote-v0.3.1/enigma2-plugin-extensions-addremote_0.3.1_all.ipk)
- [الإصدار وملفات المصدر والبصمات](https://github.com/3bdlios/gt-panel/releases/tag/add-remote-v0.3.1)
- [المصدر والمتطلبات والقيود](../plugins/add-remote/README.md)
- https://t.me/fares3nzi

## التثبيت المباشر

نفّذ على الرسيفر:

```sh
wget -O /tmp/install-add-remote.sh https://raw.githubusercontent.com/3bdlios/gt-panel/main/install-add-remote.sh
sh /tmp/install-add-remote.sh
```

المثبت يتحقق من SHA256 ثم يستخدم opkg. لا يعيد تشغيل الواجهة تلقائيًا؛ أعد تشغيلها يدويًا حين يناسبك.

## من GT Panel

في أحدث GT Panel افتح Plugins ثم Add Remote. كتالوج v3 يطابق هوية XCONN/GTMedia GT Combo وصورة OpenATV 8.0.1.20261007 مع Python 3.14. نسخة IPK الخاصة بالبانل تضم ملفات الإضافة فقط، لأن محركه يمنع الكتابة خارج مجلدات الإضافات؛ محتوى كود الإضافة مطابق للحزمة المباشرة. لا تحتاج تحديث محرك GT Panel أو توسيع صلاحياته. المحرك يثبت الملفات مع نسخ احتياطية، ولا يسجل الحزمة عبر opkg أو يجلب الاعتمادات؛ IR الخام يستخدم مكتبة Python القياسية، وevdev اختياري لـBluetooth.

بعد الحفظ يتفعّل الملف تلقائيًا. يدعم تكرار الإطارات الكاملة وNEC repeat؛ بعض بروتوكولات toggle أو rolling codes غير مدعومة. يعمل الريموت المفعّل داخل البلجن، ويتوقف الحقن أثناء التعلم فقط.

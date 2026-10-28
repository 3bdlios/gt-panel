# Add Remote 0.3.2

إضافة Enigma2 Python 3 مجانية من Fares3nzi، بواجهة ريموت كاملة الشاشة، تعلم تلقائي لبصمات IR، ملفات تعريف متعددة، وتكرار الضغط المطول. لا تدعم كل أجهزة IR بلا استثناء.

- [حزمة IPK المباشرة](https://github.com/3bdlios/gt-panel/releases/download/add-remote-v0.3.2/enigma2-plugin-extensions-addremote_0.3.2_all.ipk)
- [الإصدار وملفات المصدر والبصمات](https://github.com/3bdlios/gt-panel/releases/tag/add-remote-v0.3.2)
- [المصدر والمتطلبات والقيود](../plugins/add-remote/README.md)
- https://t.me/fares3nzi

## التثبيت المباشر

نفّذ على الرسيفر:

```sh
wget -O /tmp/install-add-remote.sh https://raw.githubusercontent.com/3bdlios/gt-panel/main/install-add-remote.sh
sh /tmp/install-add-remote.sh
```

المثبت يتحقق من SHA256 ثم يستخدم opkg. لا يعيد تشغيل الواجهة تلقائيًا؛ أعد تشغيلها يدويًا حين يناسبك.

## علاقة الإضافة بـGT Panel

هذا إصدار مستقل يُثبّت عبر opkg فقط. لم يُضف إلى كتالوجات GT Panel، ولم يتغير كود البانل أو تحديثه أو سياسة تثبيته. وجود المصدر والملفات في المستودع لا يغير شيئًا على الأجهزة المثبت عليها البانل.

بعد الحفظ يتفعّل الملف تلقائيًا. يدعم تكرار الإطارات الكاملة وNEC repeat؛ بعض بروتوكولات toggle أو rolling codes غير مدعومة. يعمل الريموت المفعّل داخل البلجن، ويتوقف الحقن أثناء التعلم فقط.

إصدار 0.3.2 يصلح فشل تثبيت الحزمة على OpenBH عندما يتعذر تحميل python3-evdev: أزيلت التوصية الآلية بهذه المكتبة الاختيارية دون تجاهل الاعتمادات الأساسية.

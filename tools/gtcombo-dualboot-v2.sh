#!/bin/sh
exec /usr/bin/python3 - "$@" <<'XCENIGMA_PY'
import argparse,base64,hashlib,json,os,stat,sys,tempfile,time,types
from pathlib import Path
PAYLOAD = {'usr/lib/gtcombo/android-once.py': 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJWZXJpZmllZCBvbmUtc2hvdCBib290IGZsYWcuIERlZmF1bHQgLS1jaGVjayBpcyByZWFkLW9ubHkuIE5ldmVyIHJlYm9vdHMuIiIiCmltcG9ydCBhcmdwYXJzZSwgaGFzaGxpYiwganNvbiwgb3MsIHJlLCBzdGF0LCBzdHJ1Y3QsIHRlbXBmaWxlLCB6bGliCmZyb20gcGF0aGxpYiBpbXBvcnQgUGF0aApTSVpFPTY1NTM2CkJPT1RfU0hBPSdiNmYwMWRmODFlNzRhODNhNTIxNzliN2NmZGJhZjU0NjY4MzNkYWU0N2M1YjlhODIwMmQ5ZDY2ODYxZWFkMzZjJwpCT09UQ01EPWInaWYgdGVzdCAke2Jvb3Rmcm9tbmFuZH0gPSAxOyB0aGVuIHNldGVudiBib290ZnJvbW5hbmQgMDsgc2F2ZWVudjsgZWxzZSBydW4gYm9vdGZyb21zZDsgcnVuIGJvb3Rmcm9tdXNiOyBydW4gYm9vdGZyb21lbW1jOyBmaTsgcnVuIHN0b3JlYm9vdCcKClBST0ZJTEVfQ09NTUFORFM9e2Inc3RvcmVib290JzogJ2NkNzk5OGYzZDI0YmY3Mzk5MTZiZjUxYTY1OTg0NThjNTRjZmZiOGFiMzE2MjA2M2YyZGJjZjEwZDEyMWIyYTYnLCBiJ3N0b3JlYXJncyc6ICc3NzFhMjQ2Y2Y0MGVkNTYzYTBkODY2MDBkYTM4MTQzNWE5MTliYmUxMzFjYWJiOTM2MTdmZjAxY2Q4MDQxYjI2JywgYidib290ZnJvbXNkJzogJ2JkMDAyNmMzZGVjMGM4YzM0NmMxYjZjNmUwNWQyZjVjODJmY2RmY2JkODVhZGFiMDllMzYwN2RiZjMzNWIxMjcnLCBiJ2Jvb3Rmcm9tdXNiJzogJ2Y2Nzk0NjY3NjQyMjgzYmRiOTE4NGNhNzJkNzFlMDBiYmM4ZjVjZmJjNmFjNjgwMTY0YWMzYjI0MjdhZmZjMGQnLCBiJ2Jvb3Rmcm9tZW1tYyc6ICcwNzYzNTdlYjRjNWUwYzEzYTE0NDQ3MDMyY2ZlZTcwNGYxMjA4ODk5MzcxYWNkZDEwMTgxMTk0ZjczZWRiMTQ2J30KCmRlZiBzaGEoYik6IHJldHVybiBoYXNobGliLnNoYTI1NihiKS5oZXhkaWdlc3QoKQoKZGVmIHBhcnNlKHJhdyk6CiAgICBpZiBsZW4ocmF3KSE9U0laRSBvciBzdHJ1Y3QudW5wYWNrKCc8SScscmF3Wzo0XSlbMF0gIT0gemxpYi5jcmMzMihyYXdbNDpdKSYweGZmZmZmZmZmOgogICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcignSW52YWxpZCA2NEtpQiBlbnZpcm9ubWVudCBDUkMnKQogICAgZW5kPXJhdy5maW5kKGInXDBcMCcsNCkKICAgIGlmIGVuZDwwOiByYWlzZSBSdW50aW1lRXJyb3IoJ05vIGVudmlyb25tZW50IHRlcm1pbmF0b3InKQogICAgcmVzdWx0PXt9CiAgICBmb3IgZW50cnkgaW4gcmF3WzQ6ZW5kXS5zcGxpdChiJ1wwJyk6CiAgICAgICAgaWYgYic9JyBub3QgaW4gZW50cnk6IHJhaXNlIFJ1bnRpbWVFcnJvcignSW52YWxpZCBlbnZpcm9ubWVudCByZWNvcmQnKQogICAgICAgIGtleSx2YWx1ZT1lbnRyeS5zcGxpdChiJz0nLDEpCiAgICAgICAgaWYga2V5IGluIHJlc3VsdDogcmFpc2UgUnVudGltZUVycm9yKCdEdXBsaWNhdGUgZW52aXJvbm1lbnQga2V5JykKICAgICAgICByZXN1bHRba2V5XT12YWx1ZQogICAgcmV0dXJuIHJlc3VsdAoKZGVmIHBsYW4ocmF3KToKICAgIGVudj1wYXJzZShyYXcpCiAgICBpZiBlbnYuZ2V0KGInYm9vdGNtZCcpIT1CT09UQ01EOiByYWlzZSBSdW50aW1lRXJyb3IoJ0Jvb3QgY29tbWFuZCBjaGFuZ2VkOyBzdG9wIGZvciByZXZpZXcnKQogICAgaWYgZW52LmdldChiJ2Jvb3Rmcm9tbmFuZCcpIT1iJzAnOiByYWlzZSBSdW50aW1lRXJyb3IoJ09uZS1zaG90IGZsYWcgaXMgYWxyZWFkeSBzZXQgb3IgdW5rbm93bicpCiAgICBuZWVkbGU9YidcMGJvb3Rmcm9tbmFuZD0wXDAnCiAgICBpZiByYXcuY291bnQobmVlZGxlKSE9MTogcmFpc2UgUnVudGltZUVycm9yKCdBbWJpZ3VvdXMgZmxhZyBsb2NhdGlvbicpCiAgICBwYXRjaGVkPWJ5dGVhcnJheShyYXcpCiAgICBvZmZzZXQ9cmF3LmluZGV4KG5lZWRsZSkrbGVuKGInXDBib290ZnJvbW5hbmQ9JykKICAgIHBhdGNoZWRbb2Zmc2V0XT1vcmQoJzEnKQogICAgcGF0Y2hlZFs6NF09c3RydWN0LnBhY2soJzxJJyx6bGliLmNyYzMyKHBhdGNoZWRbNDpdKSYweGZmZmZmZmZmKQogICAgYWZ0ZXI9Ynl0ZXMocGF0Y2hlZCk7IGV4cGVjdGVkPWRpY3QoZW52KTsgZXhwZWN0ZWRbYidib290ZnJvbW5hbmQnXT1iJzEnCiAgICBpZiBwYXJzZShhZnRlcikhPWV4cGVjdGVkOiByYWlzZSBSdW50aW1lRXJyb3IoJ1VuZXhwZWN0ZWQgdmFyaWFibGUgY2hhbmdlJykKICAgIGlmIGFueShyYXdbaV0hPWFmdGVyW2ldIGZvciBpIGluIHJhbmdlKDQsU0laRSkgaWYgaSE9b2Zmc2V0KTogcmFpc2UgUnVudGltZUVycm9yKCdVbmV4cGVjdGVkIGJ5dGUgY2hhbmdlJykKICAgIHJldHVybiBhZnRlcixvZmZzZXQKCmRlZiB2ZXJpZnlfaG9zdCgpOgogICAgbW9kZWw9UGF0aCgnL3Byb2MvZGV2aWNlLXRyZWUvbW9kZWwnKS5yZWFkX2J5dGVzKCkucnN0cmlwKGInXDBcclxuICcpCiAgICBpZiBtb2RlbCAhPSBiJ0dUTWVkaWEgR1QgQ29tYm8nOiByYWlzZSBSdW50aW1lRXJyb3IoJ1RoaXMgcmVwYWlyIGlzIGZvciBHVE1lZGlhIEdUIENvbWJvIG9ubHknKQogICAgaWYgUGF0aCgnL3Byb2MvZGV2aWNlLXRyZWUvY29yZWVsZWMtZHQtaWQnKS5yZWFkX2J5dGVzKCkucnN0cmlwKGInXDBcclxuICcpICE9IGInc20xX3M5MDV4M19ndGNvbWJvJzogcmFpc2UgUnVudGltZUVycm9yKCdVbmV4cGVjdGVkIEdUIENvbWJvIERUIGlkZW50aXR5JykKICAgIGV4cGVjdGVkX2Jvb3Rfc2hhcz17Qk9PVF9TSEEsJ2MyMGQyYTA5NWVjMmE0YzJiMTFjYzU5ODI1ODQ5ODM1YjgxNzg4Y2ViNTAwMTIxNDUyNThiNDhjZjA3MGVkNDEnfQogICAgZm9yIG5hbWUsbWlub3IgaW4gKCgnL2Rldi9ib290bG9hZGVyJywxKSwoJy9kZXYvZW52Jyw0KSk6CiAgICAgICAgcz1vcy5zdGF0KG5hbWUpCiAgICAgICAgaWYgbm90IHN0YXQuU19JU0JMSyhzLnN0X21vZGUpIG9yIG9zLm1ham9yKHMuc3RfcmRldikhPTE3OSBvciBvcy5taW5vcihzLnN0X3JkZXYpIT1taW5vcjoKICAgICAgICAgICAgcmFpc2UgUnVudGltZUVycm9yKCdVbmV4cGVjdGVkIGJsb2NrIGRldmljZSBtYXBwaW5nOiAnK25hbWUpCiAgICB3aXRoIG9wZW4oJy9kZXYvYm9vdGxvYWRlcicsJ3JiJyxidWZmZXJpbmc9MCkgYXMgZjoKICAgICAgICBvYnNlcnZlZF9ib290X3NoYT1zaGEoZi5yZWFkKDQxOTQzMDQpKQogICAgICAgIGlmIG9ic2VydmVkX2Jvb3Rfc2hhIG5vdCBpbiBleHBlY3RlZF9ib290X3NoYXM6IHJhaXNlIFJ1bnRpbWVFcnJvcignRGlmZmVyZW50IGJvb3Rsb2FkZXI7IGRpYWdub3N0aWMgcmVwb3J0IHJlcXVpcmVkJykKICAgIGlmIG9ic2VydmVkX2Jvb3Rfc2hhID09ICdjMjBkMmEwOTVlYzJhNGMyYjExY2M1OTgyNTg0OTgzNWI4MTc4OGNlYjUwMDEyMTQ1MjU4YjQ4Y2YwNzBlZDQxJzoKICAgICAgICAjIE1hdGNoIHRoZSByZXBvcnRlZCAyR0IgR1QgQ29tYm8gcHJvZmlsZTsgdGhpcyBpcyBub3QgYmluYXJ5IGVxdWl2YWxlbmNlLgogICAgICAgIGVudj1wYXJzZShyZWFkX2VudigpKQogICAgICAgIGlmIGVudi5nZXQoYidhbWxfZHQnKSAhPSBiJ3NtMV9hYzIxM18yZyc6cmFpc2UgUnVudGltZUVycm9yKCdSZXBvcnRlZCBib290bG9hZGVyIHJlcXVpcmVzIHRoZSBtYXRjaGluZyBHVCBDb21ibyAyR0IgaWRlbnRpdHknKQogICAgICAgIGZvciBrZXksZXhwZWN0ZWQgaW4gUFJPRklMRV9DT01NQU5EUy5pdGVtcygpOgogICAgICAgICAgICBpZiBzaGEoZW52LmdldChrZXksYicnKSkhPWV4cGVjdGVkOnJhaXNlIFJ1bnRpbWVFcnJvcignQm9vdCBmbG93IGRpZmZlcnMgZnJvbSByZXBvcnRlZCBwcm9maWxlOiAnK2tleS5kZWNvZGUoKSkKICAgIG1vdW50cz1bbC5zcGxpdCgpIGZvciBsIGluIFBhdGgoJy9wcm9jL21vdW50cycpLnJlYWRfdGV4dCgpLnNwbGl0bGluZXMoKV0KICAgIHJvb3Q9bmV4dChtIGZvciBtIGluIG1vdW50cyBpZiBtWzFdPT0nLycpOyBmbGFzaD1uZXh0KG0gZm9yIG0gaW4gbW91bnRzIGlmIG1bMV09PScvZmxhc2gnKQogICAgcmRldj1vcy5wYXRoLnJlYWxwYXRoKHJvb3RbMF0pOyBmZGV2PW9zLnBhdGgucmVhbHBhdGgoZmxhc2hbMF0pCiAgICBpZiBub3QgcmUuZnVsbG1hdGNoKHInL2Rldi9zZFthLXpdKzInLHJkZXYpIG9yIHJlLnN1YihyJ1xkKyQnLCcnLHJkZXYpIT1yZS5zdWIocidcZCskJywnJyxmZGV2KToKICAgICAgICByYWlzZSBSdW50aW1lRXJyb3IoJ0JhY2t1cCBkaXJlY3RvcnkgbXVzdCBiZSBvbiB2ZXJpZmllZCBVU0Igcm9vdCcpCiAgICByZXR1cm4gcmRldgoKZGVmIHJlYWRfZW52KCk6CiAgICB3aXRoIG9wZW4oJy9kZXYvZW52JywncmInLGJ1ZmZlcmluZz0wKSBhcyBmOiByZXR1cm4gZi5yZWFkKFNJWkUpCgpkZWYgd3JpdGVfZXhhY3QoZmQsZGF0YSk6CiAgICBvZmY9MAogICAgd2hpbGUgb2ZmPGxlbihkYXRhKToKICAgICAgICBuPW9zLnB3cml0ZShmZCxkYXRhW29mZjpdLG9mZikKICAgICAgICBpZiBuPD0wOiByYWlzZSBSdW50aW1lRXJyb3IoJ1Nob3J0IGRldmljZSB3cml0ZScpCiAgICAgICAgb2ZmKz1uCiAgICBvcy5mc3luYyhmZCkKCmRlZiBtYWluKCk6CiAgICBhcD1hcmdwYXJzZS5Bcmd1bWVudFBhcnNlcihkZXNjcmlwdGlvbj1fX2RvY19fKQogICAgYXAuYWRkX2FyZ3VtZW50KCctLWFybScsYWN0aW9uPSdzdG9yZV90cnVlJyxoZWxwPSdXcml0ZXMgaW50ZXJuYWwgZW52aXJvbm1lbnQgYWZ0ZXIgdmVyaWZpZWQgYmFja3VwJykKICAgIGFwLmFkZF9hcmd1bWVudCgnLS1leHBlY3Qtc2hhMjU2JyxoZWxwPSdFeGFjdCBvcmlnaW5hbCBlbnZpcm9ubWVudCBoYXNoIGZyb20gdGhlIHJlYWQtb25seSBjaGVjaycpCiAgICBhcC5hZGRfYXJndW1lbnQoJy0tY2hlY2snLGFjdGlvbj0nc3RvcmVfdHJ1ZScpCiAgICBhcmdzPWFwLnBhcnNlX2FyZ3MoKQogICAgaWYgYXJncy5hcm0gYW5kIGFyZ3MuY2hlY2s6IHJhaXNlIFJ1bnRpbWVFcnJvcignU2VsZWN0IGNoZWNrIG9yIGFybScpCiAgICByb290PXZlcmlmeV9ob3N0KCk7IGJlZm9yZT1yZWFkX2VudigpOyBhZnRlcixvZmZzZXQ9cGxhbihiZWZvcmUpCiAgICBwcmludCgnQk9PVExPQURFUiBNQVRDSDsgRU5WIENSQyBWQUxJRDsgVVNCIFJPT1Q6Jyxyb290KQogICAgcHJpbnQoJ0VOVl9TSEEyNTY6JyxzaGEoYmVmb3JlKSkKICAgIHByaW50KCdORVdfRU5WX1NIQTI1NjonLHNoYShhZnRlcikpCiAgICBwcmludCgnUExBTjogYm9vdGZyb21uYW5kIDAgLT4gMSBhdCBkYXRhIGJ5dGUnLG9mZnNldCwncGx1cyBmb3VyIENSQyBieXRlczsgbm8gb3RoZXIgdmFyaWFibGVzIGNoYW5nZWQuJykKICAgIHByaW50KCdFeGlzdGluZyBib290Y21kIHJlc2V0cyB0aGUgZmxhZyB0byAwIGJlZm9yZSBhdHRlbXB0aW5nIGludGVybmFsIEFuZHJvaWQuJykKICAgIGlmIG5vdCBhcmdzLmFybToKICAgICAgICBwcmludCgnQ0hFQ0sgT05MWTogbm90aGluZyB3cml0dGVuLicpOyByZXR1cm4KICAgIGlmIG9zLmdldGV1aWQoKSE9MCBvciBhcmdzLmV4cGVjdF9zaGEyNTYhPXNoYShiZWZvcmUpOgogICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcignUm9vdCBhbmQgbWF0Y2hpbmcgLS1leHBlY3Qtc2hhMjU2IHJlcXVpcmVkIGJlZm9yZSB3cml0aW5nJykKICAgIGJhY2t1cD1QYXRoKHRlbXBmaWxlLm1rZHRlbXAocHJlZml4PSdndGNvbWJvLWVudi1iYWNrdXAtJyxkaXI9Jy9ldGMnKSkKICAgIG9zLmNobW9kKGJhY2t1cCwwbzcwMCkKICAgIGZvciBuYW1lLGRhdGEgaW4gKCgnZW52LWJlZm9yZS5iaW4nLGJlZm9yZSksKCdlbnYtYXJtZWQuYmluJyxhZnRlcikpOgogICAgICAgIHdpdGggKGJhY2t1cC9uYW1lKS5vcGVuKCd4YicpIGFzIGY6IGYud3JpdGUoZGF0YSk7IGYuZmx1c2goKTsgb3MuZnN5bmMoZi5maWxlbm8oKSkKICAgICAgICBpZiAoYmFja3VwL25hbWUpLnJlYWRfYnl0ZXMoKSE9ZGF0YTogcmFpc2UgUnVudGltZUVycm9yKCdCYWNrdXAgdmVyaWZpY2F0aW9uIGZhaWxlZCcpCiAgICBtZXRhPXsnZGV2aWNlJzonL2Rldi9lbnYnLCdvZmZzZXQnOjAsJ2xlbmd0aCc6U0laRSwnb3JpZ2luYWxfc2hhMjU2JzpzaGEoYmVmb3JlKSwnYXJtZWRfc2hhMjU2JzpzaGEoYWZ0ZXIpLCdib290bG9hZGVyX3NoYTI1Nic6aGFzaGxpYi5zaGEyNTYoUGF0aCgnL2Rldi9ib290bG9hZGVyJykub3BlbigncmInKS5yZWFkKDQxOTQzMDQpKS5oZXhkaWdlc3QoKX0KICAgIHdpdGggKGJhY2t1cC8nbWV0YWRhdGEuanNvbicpLm9wZW4oJ3gnKSBhcyBmOgogICAgICAgIGpzb24uZHVtcChtZXRhLGYsaW5kZW50PTIpOyBmLmZsdXNoKCk7IG9zLmZzeW5jKGYuZmlsZW5vKCkpCiAgICBvcy5zeW5jKCk7IHByaW50KCdWRVJJRklFRCBCQUNLVVA6JyxiYWNrdXAsZmx1c2g9VHJ1ZSkKICAgIGZkPW9zLm9wZW4oJy9kZXYvZW52Jyxvcy5PX1JEV1J8b3MuT19TWU5DKQogICAgdHJ5OgogICAgICAgIGlmIG9zLnByZWFkKGZkLFNJWkUsMCkhPWJlZm9yZTogcmFpc2UgUnVudGltZUVycm9yKCdFbnZpcm9ubWVudCBjaGFuZ2VkIGFmdGVyIHJldmlldzsgcmVmdXNpbmcgd3JpdGUnKQogICAgICAgIHRyeToKICAgICAgICAgICAgd3JpdGVfZXhhY3QoZmQsYWZ0ZXIpCiAgICAgICAgICAgIGlmIG9zLnByZWFkKGZkLFNJWkUsMCkhPWFmdGVyOiByYWlzZSBSdW50aW1lRXJyb3IoJ0FybWVkIGVudmlyb25tZW50IHJlYWRiYWNrIG1pc21hdGNoJykKICAgICAgICBleGNlcHQgRXhjZXB0aW9uOgogICAgICAgICAgICBwcmludCgnV3JpdGUgZmFpbGVkOyBhdHRlbXB0aW5nIHRvIHJlc3RvcmUgdmVyaWZpZWQgb3JpZ2luYWwuJyxmbHVzaD1UcnVlKQogICAgICAgICAgICB3cml0ZV9leGFjdChmZCxiZWZvcmUpCiAgICAgICAgICAgIGlmIG9zLnByZWFkKGZkLFNJWkUsMCkhPWJlZm9yZTogcmFpc2UgUnVudGltZUVycm9yKCdDUklUSUNBTDogcmVzdG9yZSByZWFkYmFjayBmYWlsZWQ7IGRvIG5vdCByZWJvb3QnKQogICAgICAgICAgICByYWlzZQogICAgZmluYWxseTogb3MuY2xvc2UoZmQpCiAgICBwcmludCgnQVJNRUQgQU5EIFJFQURCQUNLIFZFUklGSUVELiBObyByZWJvb3QgcGVyZm9ybWVkLicpCiAgICBwcmludCgnS2VlcCB0aGlzIGJhY2t1cDsgZG8gbm90IGFybSBhZ2Fpbi4gTmV4dCBub3JtYWwgcmVib290IHNob3VsZCBieXBhc3MgVVNCIG9uY2UuJykKCmlmIF9fbmFtZV9fPT0nX19tYWluX18nOgogICAgdHJ5OiBtYWluKCkKICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZTogcHJpbnQoJ1NUT1A6JyxlKTsgcmFpc2UgU3lzdGVtRXhpdCgxKQo=', 'usr/lib/gtcombo/android-boot.py': 'IyEvdXNyL2Jpbi9lbnYgcHl0aG9uMwoiIiJTaGFyZWQgb25lLXNob3QgQW5kcm9pZCBoZWxwZXI7IGNhbGxlcnMgbXVzdCBvYnRhaW4gYW4gZXhwbGljaXQgQW5kcm9pZCBjaG9pY2UuIiIiCmltcG9ydCBpbXBvcnRsaWIudXRpbCwgb3MsIHN1YnByb2Nlc3MsIHN5cwpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKVE9PTD1QYXRoKCcvdXNyL2xpYi9ndGNvbWJvL2FuZHJvaWQtb25jZS5weScpCmRlZiBtYWluKCk6CiAgICBpZiBsZW4oc3lzLmFyZ3YpIT0yIG9yIHN5cy5hcmd2WzFdIG5vdCBpbiAoJy0tYXJtJywnLS1jaGVjaycpOgogICAgICAgIHJhaXNlIFJ1bnRpbWVFcnJvcignVXNlIC0tYXJtIG9yIC0tY2hlY2s7IG5vIGF1dG9tYXRpYyBjYW5jZWwvZW52aXJvbm1lbnQgd3JpdGUnKQogICAgc3BlYz1pbXBvcnRsaWIudXRpbC5zcGVjX2Zyb21fZmlsZV9sb2NhdGlvbignZ3RfYW5kcm9pZF9vbmNlJyxzdHIoVE9PTCkpCiAgICBtPWltcG9ydGxpYi51dGlsLm1vZHVsZV9mcm9tX3NwZWMoc3BlYyk7IHNwZWMubG9hZGVyLmV4ZWNfbW9kdWxlKG0pCiAgICBtLnZlcmlmeV9ob3N0KCk7IHJhdz1tLnJlYWRfZW52KCk7IG0ucGxhbihyYXcpCiAgICBpZiBzeXMuYXJndlsxXT09Jy0tY2hlY2snOgogICAgICAgIHByaW50KCdBTkRST0lEX0hFTFBFUl9DSEVDS19PSzogbm8gY2hhbmdlcycpOyByZXR1cm4KICAgIGxvZz1QYXRoKCcvZXRjL2d0Y29tYm8tYW5kcm9pZC1sYXN0LXJlcXVlc3QubG9nJykKICAgIGlmIGxvZy5pc19zeW1saW5rKCk6cmFpc2UgUnVudGltZUVycm9yKCdVbmV4cGVjdGVkIGxvZyBzeW1saW5rJykKICAgIHdpdGggbG9nLm9wZW4oJ2EnKSBhcyBmOgogICAgICAgIGYud3JpdGUoJ0FORFJPSURfUkVRVUVTVF9TRUxFQ1RFRFxuJyk7IGYuZmx1c2goKTsgb3MuZnN5bmMoZi5maWxlbm8oKSkKICAgICAgICByZXN1bHQ9c3VicHJvY2Vzcy5ydW4oWycvdXNyL2Jpbi9weXRob24zJyxzdHIoVE9PTCksJy0tYXJtJywnLS1leHBlY3Qtc2hhMjU2JyxtLnNoYShyYXcpXSxzdGRvdXQ9ZixzdGRlcnI9c3VicHJvY2Vzcy5TVERPVVQpCiAgICAgICAgZi53cml0ZSgnUkVTVUxUPSVkXG4nJXJlc3VsdC5yZXR1cm5jb2RlKTsgZi5mbHVzaCgpOyBvcy5mc3luYyhmLmZpbGVubygpKQogICAgaWYgcmVzdWx0LnJldHVybmNvZGU6cmFpc2UgUnVudGltZUVycm9yKCdDb3VsZCBub3QgcHJlcGFyZSBBbmRyb2lkLiBMb2c6ICcrc3RyKGxvZykpCiAgICBwcmludCgnQU5EUk9JRF9PTkNFX0FSTUVEJyxmbHVzaD1UcnVlKQppZiBfX25hbWVfXz09J19fbWFpbl9fJzoKICAgIHRyeTptYWluKCkKICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZTpwcmludCgnQU5EUk9JRF9CT09UX0VSUk9SOicsZSxmaWxlPXN5cy5zdGRlcnIpO3N5cy5leGl0KDEpCg==', 'etc/init.d/gtcombo-boot-menu': 'IyEvYmluL3NoClsgIiQxIiA9IHN0b3AgXSAmJiBleGl0IDAKWyAtZSAvcnVuL2d0LWJvb3QtbWVudS1zaG93biBdICYmIGV4aXQgMAp0b3VjaCAvcnVuL2d0LWJvb3QtbWVudS1zaG93bgovdXNyL2Jpbi9weXRob24zIC91c3IvbGliL2d0Y29tYm8vYm9vdC1tZW51LnB5ID4+L3RtcC9ndC1ib290LW1lbnUubG9nIDI+JjEKcmVzdWx0PSQ/CmlmIFsgIiRyZXN1bHQiID0gMTAgXTsgdGhlbgogaWYgL3Vzci9iaW4vcHl0aG9uMyAvdXNyL2xpYi9ndGNvbWJvL2FuZHJvaWQtYm9vdC5weSAtLWFybSA+Pi90bXAvZ3QtYm9vdC1tZW51LmxvZyAyPiYxOyB0aGVuCiAgc3luYwogIC9zYmluL3JlYm9vdCAtZgogZmkKZmkKZXhpdCAwCg==', 'usr/lib/enigma2/python/Plugins/SystemPlugins/GTAndroidBoot/plugin.py': 'IiIiR1QgQ29tYm8gQW5kcm9pZCByZXN0YXJ0OiByZXRhaW4gbmF0aXZlIHNodXRkb3duIGNoZWNrcyBhbmQgZGVmZXIgZXJyb3IgZGlhbG9ncy4iIiIKaW1wb3J0IHN1YnByb2Nlc3MKZnJvbSBlbmlnbWEgaW1wb3J0IGVUaW1lcgpmcm9tIFBsdWdpbnMuUGx1Z2luIGltcG9ydCBQbHVnaW5EZXNjcmlwdG9yCmZyb20gU2NyZWVucy5TdGFuZGJ5IGltcG9ydCBUcnlRdWl0TWFpbmxvb3AsIFFVSVRfUkVCT09UCmZyb20gU2NyZWVucy5NZXNzYWdlQm94IGltcG9ydCBNZXNzYWdlQm94CgpfcGVuZGluZ19lcnJvcnM9W10KZGVmIHJ1bl9oZWxwZXIobW9kZSk6CiAgICB0cnk6CiAgICAgICAgcmVzdWx0PXN1YnByb2Nlc3MucnVuKFsnL3Vzci9iaW4vcHl0aG9uMycsJy91c3IvbGliL2d0Y29tYm8vYW5kcm9pZC1ib290LnB5Jyxtb2RlXSxjYXB0dXJlX291dHB1dD1UcnVlLHRleHQ9VHJ1ZSx0aW1lb3V0PTMwKQogICAgICAgIGlmIHJlc3VsdC5yZXR1cm5jb2RlOgogICAgICAgICAgICByZXR1cm4gKHJlc3VsdC5zdGRlcnIgb3IgcmVzdWx0LnN0ZG91dCBvciAnQW5kcm9pZCBoZWxwZXIgZmFpbGVkJykuc3RyaXAoKVstMjAwMDpdCiAgICAgICAgcmV0dXJuIE5vbmUKICAgIGV4Y2VwdCBFeGNlcHRpb24gYXMgZXJyb3I6CiAgICAgICAgcmV0dXJuIHN0cihlcnJvcikKCmRlZiBlcnJvcl9sYXRlcihzZXNzaW9uLG1lc3NhZ2UpOgogICAgIyBBIFRyeVF1aXRNYWlubG9vcCBjb25zdHJ1Y3RvciBjYW4gaW52b2tlIGNsb3NlKFRydWUpIGJlZm9yZSBiZWNvbWluZyBtb2RhbC4KICAgICMgV2FpdCBmb3IgU2Vzc2lvbiB0byByZXN0b3JlIGFuIGV4ZWN1dGFibGUgc2NyZWVuIGJlZm9yZSBvcGVuaW5nIGEgZGlhbG9nLgogICAgdGltZXI9ZVRpbWVyKCk7ZW50cnk9W3RpbWVyLDBdO19wZW5kaW5nX2Vycm9ycy5hcHBlbmQoZW50cnkpCiAgICBkZWYgZGlzcGxheSgpOgogICAgICAgIGVudHJ5WzFdKz0xCiAgICAgICAgZGlhbG9nPWdldGF0dHIoc2Vzc2lvbiwnY3VycmVudF9kaWFsb2cnLE5vbmUpCiAgICAgICAgaWYgZ2V0YXR0cihzZXNzaW9uLCdpbl9leGVjJyxGYWxzZSkgYW5kIGRpYWxvZyBpcyBub3QgTm9uZSBhbmQgZ2V0YXR0cihkaWFsb2csJ2V4ZWNpbmcnLEZhbHNlKToKICAgICAgICAgICAgdGltZXIuc3RvcCgpO19wZW5kaW5nX2Vycm9ycy5yZW1vdmUoZW50cnkpCiAgICAgICAgICAgIHNlc3Npb24ub3BlbihNZXNzYWdlQm94LCdDYW5ub3QgcHJlcGFyZSBBbmRyb2lkIGJvb3Q6XG4nK21lc3NhZ2UsdHlwZT1NZXNzYWdlQm94LlRZUEVfRVJST1IpCiAgICAgICAgZWxpZiBlbnRyeVsxXTwyMDA6CiAgICAgICAgICAgIHRpbWVyLnN0YXJ0KDUwLFRydWUpCiAgICAgICAgZWxzZToKICAgICAgICAgICAgdGltZXIuc3RvcCgpO19wZW5kaW5nX2Vycm9ycy5yZW1vdmUoZW50cnkpCiAgICAgICAgICAgIHByaW50KCdbR1RBbmRyb2lkQm9vdF0gQ2Fubm90IGRpc3BsYXkgQW5kcm9pZCBib290IGVycm9yOicsbWVzc2FnZSkKICAgIHRpbWVyLmNhbGxiYWNrLmFwcGVuZChkaXNwbGF5KTt0aW1lci5zdGFydCg1MCxUcnVlKQoKY2xhc3MgQW5kcm9pZFJlc3RhcnQoVHJ5UXVpdE1haW5sb29wKToKICAgIGRlZiBjbG9zZShzZWxmLHZhbHVlKToKICAgICAgICBpZiB2YWx1ZToKICAgICAgICAgICAgZXJyb3I9cnVuX2hlbHBlcignLS1hcm0nKQogICAgICAgICAgICBpZiBlcnJvcjoKICAgICAgICAgICAgICAgIHJlc3VsdD1UcnlRdWl0TWFpbmxvb3AuY2xvc2Uoc2VsZixGYWxzZSkKICAgICAgICAgICAgICAgIGVycm9yX2xhdGVyKHNlbGYuc2Vzc2lvbixlcnJvcikKICAgICAgICAgICAgICAgIHJldHVybiByZXN1bHQKICAgICAgICByZXR1cm4gVHJ5UXVpdE1haW5sb29wLmNsb3NlKHNlbGYsdmFsdWUpCgpkZWYgcmVzdGFydChzZXNzaW9uLCoqa3dhcmdzKToKICAgICMgQ2hlY2sgZnJvbSB0aGUgZnVsbHkgYWN0aXZlIG1lbnUsIGJlZm9yZSBjb25zdHJ1Y3RpbmcgVHJ5UXVpdE1haW5sb29wLgogICAgZXJyb3I9cnVuX2hlbHBlcignLS1jaGVjaycpCiAgICBpZiBlcnJvcjoKICAgICAgICBzZXNzaW9uLm9wZW4oTWVzc2FnZUJveCwnQ2Fubm90IHByZXBhcmUgQW5kcm9pZCBib290OlxuJytlcnJvcix0eXBlPU1lc3NhZ2VCb3guVFlQRV9FUlJPUikKICAgICAgICByZXR1cm4KICAgIHNlc3Npb24ub3BlbihBbmRyb2lkUmVzdGFydCxRVUlUX1JFQk9PVCkKCmRlZiBtZW51KG1lbnVpZCwqKmt3YXJncyk6CiAgICBpZiBtZW51aWQ9PSdzaHV0ZG93bic6cmV0dXJuIFsoJ1Jlc3RhcnQgdG8gQW5kcm9pZCcscmVzdGFydCwnZ3RfYW5kcm9pZF9yZXN0YXJ0Jyw0NSldCiAgICByZXR1cm4gW10KCmRlZiBQbHVnaW5zKCoqa3dhcmdzKToKICAgIHJldHVybiBbUGx1Z2luRGVzY3JpcHRvcihuYW1lPSdHVCBBbmRyb2lkIHJlc3RhcnQnLGRlc2NyaXB0aW9uPSdWZXJpZmllZCBvbmUtc2hvdCBBbmRyb2lkIGJvb3QgZnJvbSBVU0InLHdoZXJlPVBsdWdpbkRlc2NyaXB0b3IuV0hFUkVfTUVOVSxmbmM9bWVudSldCg==', 'usr/lib/enigma2/python/Plugins/SystemPlugins/GTAndroidBoot/__init__.py': ''}
ROOT=Path('/')
LINK='etc/rcS.d/S40gtcombo-boot-menu'
LINK_TARGET='../init.d/gtcombo-boot-menu'
BASE='etc/xcenigma-backups/gtcombo-dualboot-v2'

def digest(data):return hashlib.sha256(data).hexdigest()
def target(rel):return ROOT/rel

def check_parents(p):
    for q in p.parents:
        if q.is_symlink():raise RuntimeError('Unexpected parent symlink: '+str(q))
        if q.exists() and not q.is_dir():raise RuntimeError('Parent is not a directory: '+str(q))

def snapshot(p):
    check_parents(p)
    if p.is_symlink():return {'kind':'link','link':os.readlink(p)}
    if not p.exists():return {'kind':'absent'}
    if not p.is_file():raise RuntimeError('Not a regular file: '+str(p))
    data=p.read_bytes()
    return {'kind':'file','sha256':digest(data),'mode':stat.S_IMODE(p.stat().st_mode)}

def atomic(p,data,mode):
    check_parents(p)
    fd,name=tempfile.mkstemp(prefix='.xc-dualboot-',dir=str(p.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fchmod(f.fileno(),mode);os.fsync(f.fileno())
        os.replace(name,p)
        if p.read_bytes()!=data:raise RuntimeError('Readback failed: '+str(p))
    finally:
        if os.path.exists(name):os.unlink(name)

def payload():
    data={k:base64.b64decode(v,validate=True) for k,v in PAYLOAD.items()}
    for rel,content in data.items():
        if rel.endswith('.py'):compile(content,rel,'exec')
    return data

def preflight(data):
    if os.geteuid()!=0:raise RuntimeError('Run as root on the receiver')
    if not target('usr/bin/enigma2').is_file():raise RuntimeError('Run from Enigma2, not Android or a PC')
    m=types.ModuleType('xc_dualboot_check')
    exec(compile(data['usr/lib/gtcombo/android-once.py'],'android-once.py','exec'),m.__dict__)
    model=Path('/proc/device-tree/model').read_bytes().rstrip(b'\0\r\n ')
    with open('/dev/bootloader','rb',buffering=0) as f:boot_sha=digest(f.read(4194304))
    print('MODEL:',model.decode(errors='replace'));print('BOOTLOADER_SHA256:',boot_sha,flush=True)
    # Preserve all tested safeguards: board/DT identity, bootloader hash, block mapping,
    # USB root, environment CRC, and existing one-shot-resetting bootcmd.
    usb=m.verify_host();before=m.read_env();m.plan(before)
    from PIL import ImageFont
    ImageFont.truetype('/usr/share/fonts/valis_enigma.ttf',20)
    if not Path('/usr/lib/gtcombo/boot-menu.py').is_file():raise RuntimeError('Existing GT Combo boot menu is missing; this targeted repair does not replace its design')
    if not Path('/dev/fb0').exists():raise RuntimeError('Framebuffer is missing')
    if not Path('/dev/input').is_dir():raise RuntimeError('Remote input devices are missing')
    print('USB_ROOT:',usb);print('ENV_SHA256:',digest(before))
    print('CHECK_OK: both entry points use the verified one-shot Android helper.')
    print('No environment bytes were written; no reboot was requested.')

def state_for(data):
    result={}
    for rel,content in data.items():
        old=snapshot(target(rel))
        if old['kind']=='link':raise RuntimeError('Unexpected target symlink: '+rel)
        result[rel]={'before':old,'after':{'kind':'file','sha256':digest(content),'mode':0o755 if rel.endswith('.py') or rel.startswith('etc/init.d/') else 0o644}}
    old=snapshot(target(LINK))
    if old['kind'] not in ('absent','link') or old.get('link',LINK_TARGET)!=LINK_TARGET:raise RuntimeError('Unexpected boot-menu startup entry')
    result[LINK]={'before':old,'after':{'kind':'link','link':LINK_TARGET}}
    return result

def save_manifest(b,manifest):
    atomic(b/'manifest.json',json.dumps(manifest,indent=2).encode(),0o600)

def restore(b):
    check_parents(b/'manifest.json')
    if b.is_symlink() or b.parent!=target(BASE):raise RuntimeError('Backup must be under /'+BASE)
    if (b/'manifest.json').is_symlink():raise RuntimeError('Unexpected manifest symlink')
    manifest=json.loads((b/'manifest.json').read_text())
    entries=manifest['entries']
    if set(entries)!=set(PAYLOAD)|{LINK}:raise RuntimeError('Unexpected backup target list')
    # Validate all current files and all original copies before restoring any file.
    for rel,item in entries.items():
        now=snapshot(target(rel))
        if now!=item['before'] and now!=item['after']:raise RuntimeError('File changed since installation; refusing rollback: '+rel)
        if item['before']['kind']=='file':
            saved=b/'files'/rel
            check_parents(saved)
            if saved.is_symlink() or digest(saved.read_bytes())!=item['before']['sha256']:raise RuntimeError('Backup checksum mismatch: '+rel)
    for rel,item in reversed(list(entries.items())):
        p=target(rel);old=item['before']
        if snapshot(p)==old:continue
        if old['kind']=='file':atomic(p,(b/'files'/rel).read_bytes(),old['mode'])
        elif old['kind']=='link':
            if p.exists() or p.is_symlink():p.unlink()
            p.symlink_to(old['link'])
        else:p.unlink()
    for rel in reversed(manifest.get('created_dirs',[])):
        p=target(rel)
        if p.is_dir() and not p.is_symlink():
            try:p.rmdir()
            except OSError:pass
    manifest['status']='restored';save_manifest(b,manifest);os.sync()
    print('RESTORED:',b);print('No reboot performed. Reload Enigma2 when convenient.')

def install(data):
    entries=state_for(data)
    if all(v['before']==v['after'] for v in entries.values()):
        print('ALREADY_INSTALLED: no files changed.');return
    base=target(BASE);check_parents(base/'probe');base.mkdir(parents=True,exist_ok=True,mode=0o700)
    b=Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%d-%H%M%S-'),dir=base));os.chmod(b,0o700)
    created=[]
    for rel,item in entries.items():
        if item['before']['kind']=='file':
            dst=b/'files'/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            data_before=target(rel).read_bytes()
            if digest(data_before)!=item['before']['sha256']:raise RuntimeError('File changed before backup: '+rel)
            atomic(dst,data_before,0o600)
    manifest={'version':1,'status':'prepared','entries':entries,'created_dirs':created};save_manifest(b,manifest);os.sync()
    print('VERIFIED_BACKUP:',b,flush=True)
    try:
        for rel,item in entries.items():
            p=target(rel)
            if snapshot(p)!=item['before']:raise RuntimeError('File changed during installation: '+rel)
            missing=[];parent=p.parent
            while not parent.exists():missing.append(parent);parent=parent.parent
            for q in reversed(missing):
                q.mkdir(mode=0o755);created.append(str(q.relative_to(ROOT)))
            manifest['created_dirs']=created;save_manifest(b,manifest)
            if rel==LINK:
                if p.is_symlink():p.unlink()
                p.symlink_to(LINK_TARGET)
            else:atomic(p,data[rel],item['after']['mode'])
            if snapshot(p)!=item['after']:raise RuntimeError('Installed verification failed: '+rel)
        manifest['status']='installed';save_manifest(b,manifest);os.sync()
    except BaseException:
        print('Installation failed; restoring backed-up files.',file=sys.stderr,flush=True)
        restore(b);raise
    print('INSTALLED_AND_VERIFIED. Both boot choices are enabled for the next startup.')
    print('Android restart entry is loaded on the next Enigma2 GUI restart.')
    print('ROLLBACK: sh /tmp/gtcombo-dualboot-v2.sh --rollback '+str(b))
    print('No bootloader, DTB, partition table, channel list, or environment was modified.')
    print('No reboot performed.')

def main():
    ap=argparse.ArgumentParser(description='GT Combo dual-boot repair v2 for the reported 2GB profile and original supported GT Combo')
    group=ap.add_mutually_exclusive_group();group.add_argument('--check',action='store_true');group.add_argument('--install',action='store_true');group.add_argument('--rollback',metavar='BACKUP_DIRECTORY')
    args=ap.parse_args()
    if args.rollback:
        if os.geteuid()!=0:raise RuntimeError('Root required')
        restore(Path(args.rollback));return
    print('GT COMBO REPAIR V2: report-based compatibility candidate; remote Android boot not yet verified.')
    data=payload();preflight(data)
    if args.install or not args.check:install(data)
    else:print('CHECK ONLY. To install: sh /tmp/gtcombo-dualboot-v2.sh --install')

if __name__=='__main__':
    import contextlib,io
    capture=io.StringIO()
    class Tee:
        def __init__(self,stream):self.stream=stream
        def write(self,value):capture.write(value);return self.stream.write(value)
        def flush(self):self.stream.flush()
    status='ok';exit_code=0
    try:
        with contextlib.redirect_stdout(Tee(sys.stdout)),contextlib.redirect_stderr(Tee(sys.stderr)):
            main()
    except Exception as error:
        status='failed';exit_code=1
        line='STOP: '+str(error)
        capture.write(line+'\n');print(line,file=sys.stderr)
    result={'format':'gtcombo-dualboot-repair-result-v2','status':status,'mode':'check' if '--check' in sys.argv else 'rollback' if '--rollback' in sys.argv else 'install','output':capture.getvalue(),'reboot_requested':False,'environment_written_by_installer':False}
    p=Path('/tmp/gtcombo-dualboot-result.json')
    if p.exists() or p.is_symlink():p=p.with_name('gtcombo-dualboot-result-'+str(os.getpid())+'.json')
    try:
        fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
        print('RESULT_FILE:',p)
    except Exception as error:
        print('Could not save result file:',error,file=sys.stderr);exit_code=1
    sys.exit(exit_code)

XCENIGMA_PY

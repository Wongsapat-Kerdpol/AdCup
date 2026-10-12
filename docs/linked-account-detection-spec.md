# Spec: Linked Account Detection (ระบบจับบัญชีที่เป็นคนเดียวกัน)

> เอกสารนี้คือ **แหล่งความจริงเดียว (single source of truth)** ของ feature นี้
> ทุกการตัดสินใจในนี้ตกลงกับเจ้าของงานแล้ว และเขียนขึ้นจากการวิเคราะห์ codebase AdCup เวอร์ชันก่อนหน้า
> เวอร์ชันที่จะลงมือทำจริงเปลี่ยนไปบางส่วน (ระบบจ่ายเงินและ outlook) ดูข้อ 2 ว่าส่วนไหนต้องตรวจในโค้ดจริงก่อน

---

## 0. สำหรับ Claude ที่อ่านไฟล์นี้ (อ่านก่อนทำอะไรทั้งหมด)

คุณไม่มีบริบทจาก session ก่อนหน้า ทุกอย่างที่ต้องรู้อยู่ในไฟล์นี้ ทำตามนี้:

### 0.1 กฎการทำงาน
1. **ห้ามเปลี่ยนการตัดสินใจในข้อ 3** โดยไม่ถามเจ้าของงานก่อน ถ้าโค้ดจริงทำให้ทำตามไม่ได้ ให้หยุด อธิบายว่าขัดตรงไหน และเสนอทางเลือก
2. **ข้อ 5, 8, 9 (ชื่อตาราง ชื่อ endpoint ชื่อ component) เป็นข้อเสนอ** ปรับให้เข้ากับ convention ของโค้ดจริงได้ แต่พฤติกรรมต้องเหมือนเดิม
3. ตอบเจ้าของงานเป็น**ภาษาไทย** คงศัพท์เทคนิค โค้ด และคำสั่งเป็นภาษาอังกฤษ
4. ทำทีละ phase ตามข้อ 11 ทุก phase อยู่ใน branch เดียวคือ `feature/linked-accounts` ทำ commit ให้เล็กและ review ง่าย แก้เฉพาะที่เกี่ยวข้อง ไม่ refactor ส่วนอื่น
5. ก่อนบอกว่าเสร็จ ให้**รันเทสต์จริงและแสดงผลลัพธ์จริง**
6. Workflow ที่ตกลงกับเจ้าของงาน:
   - **branch `feature/linked-accounts` สร้างไว้แล้ว** (แตกจาก `main` ที่ commit `ce0868a` ซึ่งรวม PR #3 fair payout + outlook แล้ว)
   - commit ย่อยหลายอันตาม phase · **push branch ขึ้น GitHub ได้เป็นระยะเพื่อสำรองงาน** (เจ้าของงานอนุญาตแล้ว) · ห้าม force push
   - **เปิด PR เข้า `main` ครั้งเดียว ตอนทุก phase เสร็จ** (Phase 6) และ**ถามเจ้าของงานก่อนเปิด PR**
   - PR title และ description เป็น**ภาษาอังกฤษ** (ตาม PR เดิมใน repo) ส่วน spec นี้เป็นภาษาไทย
7. จบแต่ละ session ให้**อัปเดตข้อ 13 (Progress log)** ในไฟล์นี้ session ถัดไปจะได้ทำต่อได้ทันที

### 0.2 สิ่งที่ต้องทำใน session แรก (Phase 0: สำรวจก่อนเขียนโค้ด)
1. อ่านไฟล์นี้ให้ครบ
2. ทำ checklist ในข้อ 2.2 ทีละข้อ: เปิดไฟล์จริง บันทึก path, ชื่อฟังก์ชัน และพฤติกรรมที่เจอ
3. **ยังไม่เขียนโค้ด** ส่งรายงานให้เจ้าของงานก่อน ประกอบด้วย:
   - จุดที่ต้องเชื่อมต่อ (integration points) แต่ละจุด เป็นไฟล์ไหน ฟังก์ชันไหน
   - จุดที่โค้ดจริงต่างจากที่ spec คาดไว้
   - คำถามในข้อ 12 ที่ยังไม่มีคำตอบ
4. เขียนผลสำรวจลงข้อ 2.3 ของไฟล์นี้ แล้วรอเจ้าของงานยืนยันก่อนเริ่ม Phase 1

### 0.3 สิ่งที่ Claude ต้องการจากเจ้าของงาน
- คำตอบของคำถามในข้อ 12
- การยืนยันรายงาน Phase 0 ก่อนเริ่มเขียนโค้ด
- อนุญาตก่อนเปิด PR และก่อนรีเซ็ต DB (`docker compose down -v` ลบข้อมูลใน DB ทั้งหมด)
- ช่วยทดสอบ flow ที่ต้องใช้บัญชี Google จริง (การเชื่อม YouTube ผ่าน OAuth) เพราะ Claude ล็อกอินแทนไม่ได้

---

## 1. ภาพรวม

### 1.1 ปัญหา
AdCup มีกฎ **cap per profile** คือ เพดานเงิน gross ที่ 1 คนได้จาก 1 แคมเปญ รวมทุกคลิปของคนนั้น
แต่โค้ดนับ cap ตาม `creator_id` (ต่อบัญชี) คนที่สมัคร 2 บัญชีจึงได้ cap 2 เท่า
ผลคือ pool ถูกแบ่งให้คนอื่นน้อยลง แบรนด์จ่ายซ้ำให้ผู้ชมกลุ่มเดิม และกฎที่ประกาศไว้ไม่ถูกบังคับใช้จริง

ระบบที่มีอยู่แล้วกันได้บางส่วน:
- 1 ช่อง YouTube ผูกได้แค่ 1 บัญชี
- คลิปต้องมาจากช่องของตัวเอง
- คลิปเดิมส่งซ้ำในแคมเปญเดียวกันไม่ได้

แต่ยังมีช่องที่ใช้หลบได้:
- **อีเมลที่ดูต่างแต่เป็นกล่องเดียวกัน:** Gmail ไม่สนจุดและ `+tag` เช่น `t.o.n+shorts@gmail.com` = `ton@gmail.com`
- **หลายช่องใต้ Google account เดียว:** สร้างได้ผ่าน Brand Account
- **ปลายทางรับเงินเดียวกัน:** หลายบัญชีรับเงินเข้า PromptPay หรือบัญชีธนาคารเดียวกัน

### 1.2 เป้าหมาย
1. บังคับ cap per profile ที่ระดับ**คน** อัตโนมัติ เมื่อมีหลักฐานแข็งแรง
2. รู้ว่าบัญชีเป็นคนเดียวกัน**ก่อน**เงินออกจาก pool
3. False positive ต่ำ: คนสุจริตที่ใช้ Wi-Fi หรือเครื่องร่วมกันต้องไม่ถูกลงโทษอัตโนมัติ
4. อธิบายได้: ทุกการเชื่อมบอกได้ว่าเชื่อมด้วยสัญญาณประเภทไหน
5. แก้คืนได้: admin ยืนยันหรือยกเลิกการเชื่อมได้

### 1.3 ไม่ใช่เป้าหมาย
- แบนบัญชีอัตโนมัติ
- ดึงเงินคืนอัตโนมัติ
- ใช้ machine learning หรือบริการ fingerprint แบบเสียเงิน
- จับคนที่ใช้ตัวตนของคนอื่นทั้งหมด (บัญชีธนาคาร อีเมล Google และเครื่องของเพื่อน) ต้องใช้ eKYC จริง ซึ่งอยู่นอกขอบเขต

---

## 2. Codebase: สิ่งที่รู้ และสิ่งที่ต้องตรวจ

### 2.1 สิ่งที่รู้จากเวอร์ชันก่อนหน้า (ต้องยืนยันว่ายังเป็นแบบนี้)
- **Stack:** FastAPI + SQLAlchemy + PostgreSQL / Next.js 15 + shadcn/ui / Docker Compose
- **ไม่มี migration:** ตารางสร้างด้วย `create_all` เพิ่มตารางหรือคอลัมน์แล้วต้องรีเซ็ต DB (`docker compose down -v && docker compose up --build`)
- **Models:** `User`, `Campaign` (มี `cap_per_post`, `cap_per_profile`, `total_budget`, `paid_out`), `Submission`, `Transaction` (enum `TransactionType`: `campaign_fund`, `payout`, `withdrawal`)
- **YouTube OAuth:** `routers/youtube.py` → `callback()` บล็อกช่องที่ผูกกับบัญชีอื่นแล้ว (`channel_taken`) scope อยู่ใน `services/youtube.py` (`_SCOPE = youtube.readonly`)
- **System check:** `services/verification.py` → `run_system_check()`
- **Admin review:** `routers/review.py` → `GET /api/admin/review`, `approve`, `reject`
- **Withdraw (mock):** `routers/payments.py` → `POST /api/wallet/withdraw` ยังไม่มีฟิลด์บัญชีรับเงิน
- **Auth:** `routers/auth.py` → `register` ปัจจุบันแค่ lowercase อีเมล
- **Shared helpers:** `core/deps.py` (`get_current_user`, `require_role`), `core/config.py` (ค่าคงที่ทางธุรกิจ)
- **Frontend:**
  - `lib/api.ts` (`api<T>()` แนบ JWT ให้)
  - `lib/routes.ts` (`routes`, `navByRole`, `protectedRoutes`)
  - `lib/types.ts`
  - `components/admin/review-queue.tsx`
  - `components/settings/settings-view.tsx`
  - `components/wallet/wallet-view.tsx`
- **UI ของแอปเป็นภาษาอังกฤษ** ข้อความใหม่บนหน้าเว็บจึงต้องเป็นภาษาอังกฤษด้วย
- **Tests:** `backend/tests/` (pytest)
- **Seed:** `backend/app/seed.py` มีบัญชี creator สำหรับทดสอบ

### 2.2 สิ่งที่เปลี่ยนในเวอร์ชันใหม่ (ต้องตรวจในโค้ดจริงก่อนเริ่ม)
ข้อมูลจากเพื่อนในทีม ยังไม่ได้เห็นโค้ดจริง:
- **ระบบจ่ายเงินเปลี่ยนจาก FCFS เป็นรอบรายวัน (payout rounds)** ทุกคลิปที่ approve แล้วได้เงินตามวิวที่เพิ่มขึ้น ถ้า pool ไม่พอ **ทุกคลิปได้เปอร์เซ็นต์เท่ากัน** โดยปัดเศษแบบ largest-remainder ให้ตรงสตางค์
- **ไฟล์ที่น่าจะเกี่ยวข้อง:** `backend/app/services/allocation.py` (proportional split, `first_step_reaching`), `backend/app/services/payout.py` (payout rounds + per-creator cap)
- **per-creator cap น่าจะจัดกลุ่มด้วย hash map (`creator → videos`)** แล้วแบ่ง cap ที่เหลือของแต่ละ creator ตามสัดส่วนก่อนแบ่ง pool ← **นี่คือจุดหลักที่ feature นี้ต้องเปลี่ยน key จาก creator เป็น profile group**
- **ระบบ "Is it still worth joining?" (outlook):** `services/outlook.py`, `routers/outlook.py`, `frontend/.../campaign-outlook.tsx` เอกสารของเพื่อนบอกว่า outlook **ไม่สนใจ per-creator cap**

**Checklist ของ Phase 0** (ให้ตอบทุกข้อในข้อ 2.3):
- [ ] ระบบจ่ายเงินอยู่ไฟล์ไหน ใช้ cap per profile ที่บรรทัดไหน key ที่ใช้จัดกลุ่มคืออะไร
- [ ] ฟังก์ชันแบ่งตามสัดส่วนและปัดเศษสตางค์ชื่ออะไร เรียกใช้ซ้ำสำหรับแบ่ง cap ของกลุ่มได้ไหม
- [ ] ระบบจ่ายเงิน lock แถว campaign (`FOR UPDATE`) อยู่ไหม
- [ ] payout เกิดตอนไหนบ้าง (ตอน approve? refresh-all? job รายวัน?)
- [ ] outlook ใช้ per-creator cap หรือไม่ ต้องปรับไหม (คาดว่าไม่ต้อง)
- [ ] endpoint ถอนเงิน, register, login, YouTube callback และสร้าง submission ยังอยู่ที่เดิมไหม
- [ ] มีตารางหรือฟิลด์บัญชีรับเงินแล้วหรือยัง
- [ ] `TransactionType` มีค่าอะไรบ้าง
- [ ] รันเทสต์ทั้งหมดได้ไหม ผลเป็นอย่างไร (baseline ก่อนแก้)
- [ ] seed สร้างบัญชีอะไรบ้าง

### 2.3 ผลสำรวจ Phase 0
*(Claude เขียนส่วนนี้หลังสำรวจเสร็จ)*

---

## 3. การตัดสินใจที่ตกลงแล้ว (ห้ามเปลี่ยนโดยไม่ถาม)

| # | การตัดสินใจ |
|---|---|
| D1 | **Profile = คนจริง 1 คน (ผู้รับเงิน)** จะมีกี่บัญชีหรือกี่ช่องก็นับเป็น 1 profile ต่อแคมเปญ |
| D2 | **สัญญาณแข็งแรง (strong) 3 ตัว ใช้ union อัตโนมัติ:** ปลายทางรับเงิน (PromptPay / บัญชีธนาคาร), Google account ID (`sub`), อีเมลหลัง normalize |
| D3 | **Device ID = สัญญาณปานกลาง (medium), IP = สัญญาณอ่อน (weak)** ทั้งคู่**ไม่ union** ใช้คิดคะแนนความเสี่ยงอย่างเดียว |
| D4 | **IP ไม่ใช้ union เด็ดขาด** เพราะ CGNAT และ Wi-Fi หอหรือมหาลัยมีคนเป็นร้อยใช้ IP เดียวกัน |
| D5 | **คะแนนความเสี่ยง:** device เดียวกัน +50 · IP เดียวกัน +10 (หรือ +20 ถ้าอยู่ภายใน 24 ชม. หลังสมัคร) · สมัครห่างกันไม่เกิน 10 นาที +10 · ส่งงานแคมเปญเดียวกันห่างกันไม่เกิน 1 ชม. +10 · **ได้ 50 ขึ้นไป = ติดธง** · คิดเฉพาะคู่ที่**อยู่ต่างกลุ่มและส่งงานเข้าแคมเปญเดียวกัน** |
| D6 | **Hub:** ค่าเดียวถูกใช้เกิน **3 บัญชี** (`MAX_SHARE = 3`) · **PromptPay / บัญชีธนาคาร:** ยัง union (1 ผู้รับเงิน = 1 profile) + แจ้ง admin + พักการถอนทั้งกลุ่ม (อาจเป็นบัญชีม้า) · **Google `sub`:** **ไม่ union** (อาจเป็นเอเจนซี่ที่ดูแลหลายช่อง) + แจ้ง admin · **อีเมล:** union ตามปกติ + แจ้ง admin |
| D7 | **IP ที่มีบัญชีใช้ร่วมกันเกิน 5 บัญชี ไม่นับคะแนนเลย** · device ที่ถูกใช้เกิน 3 บัญชี ไม่นับคะแนน |
| D8 | **บังคับตั้งค่าบัญชีรับเงินก่อนส่งงานครั้งแรก** เพราะเงินออกจาก pool ในรอบจ่ายถัดไปหลัง approve ถ้ารอรู้ตอนถอนจะช้าเกินไป |
| D9 | **ผลของการเชื่อมคือ "ใช้ cap ร่วมกัน" ไม่ใช่การแบน** · ไม่ปฏิเสธ submission เพราะเชื่อมบัญชีได้ (การส่งคลิปไม่ผิดกฎ การได้เงินเกิน cap ต่างหากที่ผิด) |
| D10 | **ไม่ดึงเงินคืนอัตโนมัติ** ถ้าเจอว่าเชื่อมกันหลังจ่ายเงินไปแล้ว: payout ครั้งถัดไปของกลุ่มเป็น 0 เอง + สร้างธง overage + พักการถอน + admin ตัดสินว่า Keep หรือ Reverse |
| D11 | **พักการถอน** ถ้ากลุ่มของผู้ใช้มีธง (`suspected`, `hub`, `overage`) ที่ยัง `open` |
| D12 | **Admin ตัดสินเนื้อหาคลิปเหมือนเดิม** ที่ Review queue (Approve / Reject) การยืนยันว่าเป็นคนเดียวกันเป็น**อีกเรื่องหนึ่ง** ทำที่หน้าใหม่ **Linked accounts** |
| D13 | **สัญญาณแข็งแรงไม่ต้องให้ admin ยืนยัน** ระบบรวม cap ให้เอง admin แค่เห็นกล่องเตือน |
| D14 | **เก็บเป็น HMAC-SHA256 hash เท่านั้น** ไม่เก็บค่าจริง (PDPA) ใช้ secret key ของเซิร์ฟเวอร์ เพราะ hash ธรรมดาของเบอร์โทรเดาย้อนกลับได้ง่าย · หน้า admin แสดงแค่ประเภทสัญญาณที่ตรงกัน ไม่แสดงค่าจริง |
| D15 | **เก็บสัญญาณ แล้ว rebuild กลุ่มใหม่ทั้งหมด** ทุกครั้งที่มีการเปลี่ยน เพราะ Union-Find แยกกลุ่มคืนไม่ได้ (รองรับการยกเลิก) |
| D16 | **ไม่บอกผู้ใช้ว่าโดนจับด้วยสัญญาณไหน** ฝั่ง creator เห็นแค่ข้อความกลางๆ เช่น "Cap per profile reached" หรือ "Withdrawals are on hold while we review your account" |
| D17 | **ปลายทางรับเงินเดียวกัน = คนเดียวกันเสมอ** admin ยกเลิกการเชื่อมด้วยสัญญาณนี้ไม่ได้ สัญญาณแข็งแรงอื่น (Google, อีเมล) admin สั่ง dismiss ได้ |
| D18 | **โหนดในกราฟคือบัญชี creator เท่านั้น** บัญชีแบรนด์ไม่เกี่ยว (1 บัญชีมีได้ role เดียว คนที่เป็นทั้งแบรนด์และ creator จึงต้องมี 2 บัญชี และไม่ควรโดน) |

---

## 4. สัญญาณ (Signals)

| `type` | จุดเก็บ | ความแข็งแรง | Normalize | 2 บัญชีตรงกัน | เกิน 3 บัญชี |
|---|---|---|---|---|---|
| `payout_account` | ตั้งค่าบัญชีรับเงิน | strong | PromptPay เบอร์โทร → `+66XXXXXXXXX` · PromptPay เลขบัตร → ตัวเลข 13 หลัก · ธนาคาร → `BANKCODE:digits` | union | union + hub flag + พักถอน |
| `google_sub` | YouTube OAuth callback (เพิ่ม scope `openid` แล้วอ่าน `sub` จาก `id_token`) | strong | ใช้ตามที่ได้มา | union | **ไม่ union** + hub flag |
| `email_norm` | register | strong | lowercase · ถ้าโดเมนเป็น `gmail.com` หรือ `googlemail.com`: ตัด `+tag` และจุดออกจาก local part แล้วเปลี่ยนโดเมนเป็น `gmail.com` · โดเมนอื่น: lowercase อย่างเดียว | union | union + hub flag |
| `device_id` | register, login, สร้าง submission, withdraw | medium | UUID ตามที่ได้มา | +50 คะแนน | ไม่นับ |
| `ip` | register, login, withdraw | weak | IP string | +10 / +20 คะแนน | เกิน 5 บัญชี ไม่นับ |

**Hash:** `value_hash = HMAC_SHA256(IDENTITY_HASH_SECRET, f"{type}:{normalized}")` แบบ hex
- เพิ่ม `IDENTITY_HASH_SECRET` ใน `core/config.py` และ `.env.example`

**Device ID:**
- frontend สร้าง UUID ครั้งแรก เก็บใน `localStorage` key `adcup_device_id`
- แนบ header `X-Device-Id` ไปกับทุก request ใน `lib/api.ts`
- backend อ่าน header นี้ ถ้าไม่มีให้ข้าม ไม่ error

**IP:**
- อ่านจาก `request.client.host`
- ถ้าอยู่หลัง proxy ให้ดู `X-Forwarded-For` ตาม setup จริง ถามเจ้าของงานถ้าไม่แน่ใจ

**อัปเดตแถวเดิม:** ถ้าสัญญาณเดิม (user, type, hash) มีอยู่แล้ว ให้อัปเดต `last_seen_at` เท่านั้น ไม่สร้างแถวซ้ำ

**ผู้ใช้เปลี่ยนบัญชีรับเงิน:** เก็บสัญญาณเก่าไว้เป็นประวัติ (ยังนับใน union) เพื่อกันการสลับบัญชีหลบ ถ้าโค้ดจริงทำให้ยาก ถามเจ้าของงาน

---

## 5. Data model (ข้อเสนอ ปรับชื่อตาม convention ได้)

### 5.1 `identity_signals`
| คอลัมน์ | ชนิด | หมายเหตุ |
|---|---|---|
| `id` | PK | |
| `user_id` | FK users | index |
| `type` | str(20) | ค่าในข้อ 4 |
| `value_hash` | str(64) | HMAC hex |
| `dismissed` | bool, default false | admin สั่งไม่นับ (ห้ามใช้กับ `payout_account`) |
| `first_seen_at`, `last_seen_at` | datetime tz | |

- unique: (`user_id`, `type`, `value_hash`)
- index: (`type`, `value_hash`) สำหรับหาว่าใครใช้ค่าเดียวกัน

### 5.2 `manual_links`
`id`, `user_a`, `user_b`, `kind` (`confirmed_same`), `admin_id`, `note`, `created_at`

### 5.3 `link_flags`
| คอลัมน์ | หมายเหตุ |
|---|---|
| `id` | |
| `kind` | `suspected` (สัญญาณอ่อน) / `hub` / `overage` |
| `user_a`, `user_b` | nullable (hub ใช้ `signal_type` + `value_hash` แทน) |
| `campaign_id` | nullable |
| `signal_type`, `value_hash` | ใช้กับ `hub` |
| `score` | ใช้กับ `suspected` |
| `amount` | Numeric ใช้กับ `overage` (gross ที่จ่ายเกิน) |
| `reasons` | JSON เช่น `["device_id", "ip"]` |
| `status` | `open` / `confirmed` / `dismissed` / `resolved` |
| `decided_by`, `decided_at`, `created_at` | |

### 5.4 เพิ่มใน `users`
- `profile_group_id` (int, index, nullable) = id ที่น้อยที่สุดในกลุ่ม · บัญชีที่อยู่คนเดียวใช้ id ของตัวเอง
- ข้อมูลบัญชีรับเงินสำหรับแสดงผล: `payout_method` (`promptpay` / `bank`), `payout_bank_code`, `payout_account_masked` (เช่น `••• 5678`) และ `payout_account_name`
  - ค่าเต็มเก็บเป็น hash ใน `identity_signals` เท่านั้น
  - หรือทำเป็นตารางแยกก็ได้ ถ้าเวอร์ชันใหม่มีอยู่แล้วให้ใช้ของเดิม

### 5.5 ป้ายบน submission
ไม่ต้องเพิ่มคอลัมน์ ให้**คำนวณตอนอ่าน**ใน review queue ว่ามีบัญชีอื่นในกลุ่มเดียวกันอยู่ในแคมเปญนี้หรือไม่

---

## 6. Algorithms

### 6.1 Union-Find (Disjoint Set Union)
```python
class DSU:
    def __init__(self, ids):
        self.parent = {i: i for i in ids}
        self.rank = {i: 0 for i in ids}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])   # path compression
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:                # union by rank
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
```
ความซับซ้อน: เฉลี่ย O(α(n)) ต่อครั้ง (α ≤ 4 ในทางปฏิบัติ)

### 6.2 `rebuild_profile_groups(db)`
```
ids = บัญชี creator ทั้งหมด
dsu = DSU(ids)
for (type, value_hash), users in strong signals ที่ dismissed = false, จัดกลุ่มตาม (type, value_hash):
    if len(users) < 2: continue
    if len(users) > MAX_SHARE:
        สร้าง hub flag (ถ้ายังไม่มีที่ open สำหรับ type+hash นี้)
        if type == "google_sub": continue            # D6: ไม่ union
    for u in users[1:]:
        dsu.union(users[0], u)                       # union แบบดาว: k-1 ครั้ง
for (a, b) in manual_links (confirmed_same):
    dsu.union(a, b)
group_id ของแต่ละกลุ่ม = id ที่น้อยที่สุดในกลุ่ม → เขียนลง users.profile_group_id
หลังเขียน: ตรวจ overage (ข้อ 6.4) เฉพาะกลุ่มที่เปลี่ยน
```
- **เรียกเมื่อ:** มีสัญญาณ strong ใหม่, admin ยืนยัน manual link, admin dismiss สัญญาณ
- **วิธีคำนวณ:** สร้างใหม่ทั้งหมดในหน่วยความจำ ผู้ใช้หลักพันคนใช้เวลาเป็นมิลลิวินาที (O(S·α(n)))
- **flush:** ใช้ `db.flush()` ให้ caller เป็นคน commit ตามแบบเดียวกับ service อื่นในโปรเจกต์

### 6.3 คะแนนความเสี่ยง (สัญญาณอ่อน)
- **เรียกเมื่อ:** submission ผ่าน system check (เข้า `under_review`)
- **หาคู่ที่ต้องคิด:** หาเฉพาะบัญชีที่ใช้ `device_id` หรือ `ip` ร่วมกับผู้ส่ง (ผ่าน index) แล้วกรองเหลือคู่ที่**ต่างกลุ่ม**และมีงานใน**แคมเปญเดียวกัน**
- **คิดคะแนนตาม D5** โดยไม่นับค่าที่เป็น hub ตาม D7
- **ได้ 50 ขึ้นไป:**
  - สร้าง `link_flags(kind="suspected", status="open")`
  - ถ้าคู่นี้เคยถูก `dismissed` ไปแล้ว ไม่ต้องสร้างซ้ำด้วยหลักฐานเดิม
- ไม่เปลี่ยน `profile_group_id` จนกว่า admin จะยืนยัน

### 6.4 ตรวจยอดจ่ายเกิน (overage)
หลัง rebuild ตรวจกลุ่มที่มีสมาชิกเปลี่ยน:
- **ตรวจ:** ทุกแคมเปญที่มี `cap_per_profile` ถ้า `SUM(gross ของทั้งกลุ่มในแคมเปญ) > cap_per_profile`
- **ถ้าเกิน:**
  - สร้าง `link_flags(kind="overage", campaign_id, amount=ส่วนที่เกิน, status="open")`
  - การถอนของสมาชิกในกลุ่มถูกพักอัตโนมัติตาม D11

### 6.5 Payout คิด cap ระดับกลุ่ม (จุดเปลี่ยนหลักในระบบจ่ายเงิน)
หลักการ: **ใช้โค้ดจ่ายเงินเดิมทั้งหมด เปลี่ยนแค่ key ที่ใช้จัดกลุ่มสำหรับ cap per profile จาก `creator_id` เป็น `profile_group_id`**

ในแต่ละรอบจ่าย:
1. claim ของแต่ละคลิป = (วิวใหม่ ÷ 1,000) × rate
2. ตัดด้วย cap per post (ที่เหลือของคลิปนั้น)
3. **จัดกลุ่มคลิปตาม `profile_group_id` ของ creator** (hash map) ถ้า claim รวมของกลุ่มเกิน `cap_per_profile − ยอด gross ที่กลุ่มได้ไปแล้วในแคมเปญนี้` ให้แบ่ง cap ที่เหลือให้คลิปในกลุ่ม**ตามสัดส่วน** (ใช้ฟังก์ชันแบ่งและปัดเศษสตางค์ตัวเดิม)
4. ถ้า claim รวมทุกกลุ่มเกิน pool ทุกคลิปได้เปอร์เซ็นต์เท่ากัน (logic เดิม)
5. หักค่าคอม 10% แล้วเข้า wallet (logic เดิม)

ข้อกำหนดเพิ่ม:
- `profile_group_id` เป็น null (ข้อมูลเก่า) → ใช้ `creator_id` แทน
- **outlook ไม่ต้องแก้** ถ้า Phase 0 ยืนยันว่าไม่ได้ใช้ per-creator cap

---

## 7. กฎการถอนเงินและการส่งงาน

- **ส่งงาน:**
  - ถ้า creator ยังไม่ตั้งค่าบัญชีรับเงิน → `400` "Set up your payout account in Settings first" (D8)
  - ต้องแก้ seed และ test fixtures ให้บัญชี creator ทดสอบมีบัญชีรับเงิน ไม่อย่างนั้น flow เดิมจะพัง
- **ถอนเงิน:**
  - ถ้ามี `link_flags` ที่ `open` ซึ่งเกี่ยวกับผู้ใช้หรือกลุ่มของผู้ใช้ → `409` "Withdrawals are on hold while we review your account." (D11, D16)
  - ทำการตรวจนี้หลัง lock แถว user แล้ว

---

## 8. API (ข้อเสนอ)

| Method + path | ใคร | ทำอะไร |
|---|---|---|
| `GET /api/payout-method` | creator | คืนค่าแบบ mask |
| `PUT /api/payout-method` | creator | body: `{method: "promptpay"\|"bank", promptpay_id?, bank_code?, account_number?, account_name?}` → validate → เก็บค่า mask ใน user → upsert signal `payout_account` → rebuild |
| `GET /api/admin/review` (เดิม) | admin | **เพิ่ม field:** `linked_accounts: [{user_id, display_name, matched: [signal types]}]`, `group_gross_in_campaign`, `cap_per_profile`, `open_flags: [{id, kind, reasons, score}]` |
| `GET /api/admin/links` | admin | รายการธงที่ `open` (suspected / hub / overage) + กลุ่มที่มีสมาชิก 2 คนขึ้นไป |
| `POST /api/admin/link-flags/{id}/confirm` | admin | suspected → สร้าง `manual_links` → rebuild → status `confirmed` |
| `POST /api/admin/link-flags/{id}/dismiss` | admin | status `dismissed` (ไม่ rebuild ถ้าไม่มี union) |
| `POST /api/admin/link-flags/{id}/ignore-signal` | admin | hub ของ Google / อีเมล → ตั้ง `identity_signals.dismissed = true` ของค่านั้น → rebuild → `resolved` (ห้ามใช้กับ `payout_account`) |
| `POST /api/admin/link-flags/{id}/release` | admin | hub ของ PromptPay หลังตรวจแล้ว → `resolved` (ปลดการพักถอน แต่ยังเป็นกลุ่มเดียวกัน) |
| `POST /api/admin/link-flags/{id}/resolve-overage` | admin | body `{action: "keep"\|"reverse"}` → `resolved` (ดูคำถาม Q2 ในข้อ 12 เรื่อง reverse) |

---

## 9. Frontend (ข้อความบน UI เป็นภาษาอังกฤษ)

| ที่ | สิ่งที่เพิ่ม |
|---|---|
| `lib/api.ts` | แนบ `X-Device-Id` ทุก request (สร้างใน localStorage ครอบด้วย try/catch) |
| Settings | ส่วน **Payout account** (PromptPay หรือธนาคาร) พร้อมข้อความ "Required before your first submission." แสดงค่าแบบ mask หลังบันทึก |
| Submit form | ถ้าได้ 400 เรื่องบัญชีรับเงิน ให้แสดงข้อความพร้อมลิงก์ไป Settings |
| My Submissions | คลิปที่ได้ ฿0 เพราะชน cap ของกลุ่ม แสดง "Cap per profile reached" (ไม่บอกว่าเชื่อมบัญชี) |
| Review queue (admin) | **กล่องสีแดงอมชมพู** (strong link): "Linked account. Same person as **{name} (#id)**. Matched: {types}. This person has earned ฿X of the ฿Y cap per profile in this campaign." · **กล่องสีเหลืองอำพัน** (suspected): "Possible link with **{name} (#id)**: {reasons}. Not merged. Caps are still separate. Decide in Linked accounts →" · ปุ่ม Approve / Reject เหมือนเดิม |
| หน้าใหม่ `/admin/linked-accounts` | การ์ดสำหรับธงแต่ละประเภท: suspected (ตารางหลักฐาน same/diff + ปุ่ม "Different people" / "Same person: merge caps"), hub (ปุ่ม "Agency / manager: ignore this signal" หรือ "Release withdrawals"), overage (ยอดของกลุ่ม / cap / ส่วนที่เกิน + "Keep paid amount" / "Reverse") · เพิ่มใน `navByRole.admin`, `routes`, `protectedRoutes` |
| Wallet | ถ้าถูกพัก: กล่องเตือน "Withdrawals are on hold while we review your account. This usually takes 1–2 days." และปิดปุ่ม Withdraw |

ต้นแบบหน้าจอดูได้ที่ artifact ในข้อ 14 (แท็บ "ซีนจริง")

---

## 10. กรณีทดสอบ (ต้องมีเทสต์ครอบคลุม)

### 10.1 Unit tests
- **DSU:** union เป็นทอด (A–B, B–C → A, B, C กลุ่มเดียว), path compression, union by rank, union ซ้ำไม่พัง
- **ตัวอย่าง 9 บัญชี** (ใช้ในสไลด์และ artifact ควรได้ผลตรงกัน):
  - union(1,2), union(2,3), union(4,5), union(3,4) แล้ว find(5)
  - ต้องได้กลุ่ม {1, 2, 3, 4, 5} และหลัง find(5) ต้องได้ `parent[5] = 1`
  - คู่ IP (6, 7) และคู่ device (8, 9) ไม่ union
- **normalize:**
  - `T.O.N+shorts@gmail.com` → `ton@gmail.com`
  - `a.b@googlemail.com` → `ab@gmail.com`
  - `a.b+x@hotmail.com` → `a.b+x@hotmail.com`
  - `081-234-5678` → `+66812345678`
- **HMAC:** ค่าเดียวกันได้ hash เดียวกัน, type ต่างกันได้ hash ต่างกัน
- **คะแนนความเสี่ยง:**
  - device อย่างเดียว = 50 → flag
  - IP อย่างเดียว = 10 → ไม่ flag
  - IP hub (มี 6 บัญชีใช้) → 0

### 10.2 Scenario tests (ตรงกับต้นแบบใน artifact)
| # | สถานการณ์ | ผลที่ต้องได้ |
|---|---|---|
| S1 | บัญชี #12 สมัครด้วย `t.o.n+shorts@gmail.com` ขณะที่ #1 ใช้ `ton@gmail.com` | union ทันที, `profile_group_id` = 1 ทั้งคู่, ผู้ใช้ไม่เห็นอะไรผิดปกติ |
| S2 | #1 กับ #2 มี `google_sub` เดียวกัน | กลุ่มเดียวกัน |
| S3 | #2 กับ #3 ใช้ PromptPay เดียวกัน (และ S2) | #1, #2, #3 กลุ่มเดียวกัน (เป็นทอด) |
| S4 | รูมเมตใช้ IP เดียวกัน (IP นั้นมี 37 บัญชี) ส่งแคมเปญเดียวกัน | ไม่ union ไม่มีธง cap แยกกัน |
| S5 | พี่น้องใช้ device เดียวกัน + IP บ้าน (2 บัญชี) ส่งแคมเปญเดียวกัน | คะแนน 60 → ธง `suspected` `open`, cap ยังแยก, ถอนเงินถูกพัก · admin กด dismiss → ปลดพัก · admin กด confirm → กลุ่มเดียวกัน |
| S6 | ทั้งคู่ได้เงินคนละ ฿3,000 ไปแล้ว จากนั้น #41 เปลี่ยน PromptPay มาตรงกับ #40 | union, ธง `overage` amount ฿3,000, พักถอนทั้งคู่, payout รอบถัดไปของกลุ่มในแคมเปญนั้น = ฿0 |
| S7 | `google_sub` เดียวกัน 6 บัญชี (เอเจนซี่) | ไม่ union, ธง `hub` · admin กด ignore-signal → `dismissed`, ทั้ง 6 คนยังแยกกลุ่ม |
| S8 | PromptPay เดียวกัน 5 บัญชี (บัญชีม้า) | union ทั้ง 5, ธง `hub`, พักถอนทั้งกลุ่ม |
| S9 | creator ที่ยังไม่ตั้งค่าบัญชีรับเงินส่งงาน | `400` |
| S10 | บัญชีแบรนด์กับบัญชี creator อีเมลเดียวกันหลัง normalize | ไม่ union (D18) |

### 10.3 เทสต์ payout แบบกลุ่ม (ตัวเลขตัวอย่างที่ใช้ในสไลด์)
**แคมเปญ:** pool ฿10,000 · rate ฿25 / 1,000 views · cap per post ฿1,500 · cap per profile ฿3,000

**คลิป:** จ่ายในรอบเดียว ทุกคลิปมี 80,000 วิวใหม่ (= ฿2,000 → หลัง cap per post ฿1,500)
- ton (#1): 2 คลิป
- ton_shorts (#12): 2 คลิป
- beam, cee, dao: คนละ 1 คลิป

**ไม่จัดกลุ่ม** (#1 กับ #12 คนละกลุ่ม):
- claim: #1 ฿3,000 + #12 ฿3,000 + คนละ ฿1,500 × 3 → รวม ฿10,500 > pool → ทุกคลิปได้ 95.238%
- **จ่ายรวมต้อง = ฿10,000.00 พอดี**
- ต้นได้รวมประมาณ ฿5,714.29 ส่วนคนอื่นได้คนละประมาณ ฿1,428.57
- เศษ 1 สตางค์ไปที่คลิปใดคลิปหนึ่งตามการปัดแบบ largest-remainder ของโค้ดจริง

**จัดกลุ่ม** (#1, #12 กลุ่มเดียวกัน):
- กลุ่มต้น claim ฿6,000 → ตัดเหลือ ฿3,000 แบ่งตามสัดส่วน → **คลิปละ ฿750 พอดี**
- beam, cee, dao **คนละ ฿1,500**
- **จ่ายรวม ฿7,500, pool เหลือ ฿2,500**

**ข้ามรอบ:** ทำซ้ำอีกรอบโดยกลุ่มต้นได้ไปแล้ว ฿3,000 → รอบถัดไปของกลุ่มต้นต้องได้ ฿0

---

## 11. แผนการทำงาน (phase ใน branch เดียว แล้วเปิด PR เดียวตอนจบ)

ทำตามลำดับ จบแต่ละ phase ต้องผ่านเทสต์ทั้งหมด แล้ว commit (และ push สำรองได้) ก่อนขึ้น phase ถัดไป

| Phase | ขอบเขต | เงื่อนไขว่าเสร็จ |
|---|---|---|
| **Phase 1: Signals foundation** | models (`identity_signals`, `manual_links`, `link_flags`, `users.profile_group_id`, ฟิลด์บัญชีรับเงิน) · `IDENTITY_HASH_SECRET` · service normalize + HMAC · `X-Device-Id` ใน frontend · เก็บสัญญาณที่ register / login / YouTube callback (+ scope `openid`) / withdraw | unit test normalize + HMAC ผ่าน · บัญชีใหม่มีแถว signal ครบ · เทสต์เดิมผ่าน |
| **Phase 2: Union-Find + groups** | `DSU` · `rebuild_profile_groups` (hub rule, manual links) · เรียก rebuild เมื่อมีสัญญาณ strong ใหม่ · endpoint + UI **Payout account** · บังคับก่อนส่งงาน · แก้ seed / fixtures | เทสต์ DSU + ตัวอย่าง 9 บัญชี + S1, S2, S3, S7, S8, S9, S10 ผ่าน |
| **Phase 3: Group cap in payout** | เปลี่ยน key ของ cap per profile เป็น `profile_group_id` ในระบบจ่ายเงินใหม่ · overage check หลัง rebuild | เทสต์ 10.3 ทั้งหมด + S6 ผ่าน · เทสต์ payout เดิมผ่าน |
| **Phase 4: Risk score + admin API + withdrawal hold** | คะแนนความเสี่ยงเมื่อเข้า `under_review` · endpoint ในข้อ 8 · พักการถอน · ขยาย response ของ review queue | S4, S5 + เทสต์ API ผ่าน |
| **Phase 5: Admin & creator UI** | กล่องเตือนใน Review queue · หน้า Linked accounts · ข้อความใน Wallet / My Submissions | ทดสอบ flow S1, S5, S6 บนเว็บจริง (เจ้าของงานช่วยกดทดสอบ OAuth) |
| **Phase 6: เปิด PR** | รันเทสต์ทั้งหมดอีกรอบ · รีเซ็ต DB แล้วรันแอปจาก seed ใหม่ · อัปเดต Progress log · เขียน PR description (ภาษาอังกฤษ) · **ถามเจ้าของงานก่อน** แล้วเปิด PR `feature/linked-accounts` → `main` ด้วย `gh pr create` | PR เปิดแล้ว พร้อมผลเทสต์จริงใน description |

หมายเหตุ:
**PR description (Phase 6) ต้องมี:**
- สรุป feature และลิงก์ไป `docs/linked-account-detection-spec.md`
- รายการ phase ที่ทำ และไฟล์หลักที่แก้
- **"Requires a DB reset"** (`docker compose down -v`) เพราะเพิ่มตารางและคอลัมน์ และโปรเจกต์ไม่มี migration
- ไฟล์ของคนอื่นในทีมที่แตะ (auth, payout / allocation, review, payments, youtube) เพื่อให้เจ้าของไฟล์ review
- ผลเทสต์จริง และวิธีทดสอบด้วยมือ

---

## 12. คำถามที่ต้องถามเจ้าของงานตอนเริ่ม

| # | คำถาม | ค่าที่แนะนำ |
|---|---|---|
| Q1 | ~~ชื่อ branch~~ | **ตอบแล้ว:** `feature/linked-accounts` (branch เดียว, PR เดียวตอนจบ) |
| Q2 | ปุ่ม **Reverse** (ดึงเงินคืน) ทำในรอบนี้ไหม ถ้าทำต้องเพิ่ม `TransactionType.adjustment` · ลด wallet ตาม net · คืน gross เข้า pool ของแคมเปญ | รอบแรกทำแค่ **Keep** (ปิดธง + ปลดพัก) ส่วน Reverse ไว้รอบหลัง |
| Q3 | ค่าคงที่ `MAX_SHARE = 3`, เกณฑ์ IP hub 5, เกณฑ์ติดธง 50 คะแนน ยืนยันไหม | ตามนี้ (ใส่ใน `core/config.py`) |
| Q4 | ข้อความ UI ที่เสนอในข้อ 9 ใช้ได้ไหม | ใช้ตามนี้ |
| Q5 | เรื่องที่โค้ดจริงต่างจาก spec (ได้จาก Phase 0) | ถามตามที่เจอ |

---

## 13. Progress log (Claude อัปเดตทุกครั้งที่จบ session)

| วันที่ | Session ทำอะไร | สถานะ | สิ่งที่ค้าง / ขั้นต่อไป |
|---|---|---|---|
| 2026-10-12 | เขียน spec (session วิเคราะห์เดิม) | ยังไม่เริ่ม | เริ่ม Phase 0 ใน repo ใหม่ |
| 2026-10-12 | clone repo ลง `project_AdCup_101226` · สร้าง branch `feature/linked-accounts` จาก `main` (`ce0868a`) · commit spec นี้ · push branch | Phase 0 ยังไม่เริ่ม | session ใหม่: เริ่ม Phase 0 (ดู `START-HERE.md` ที่ root ของโฟลเดอร์) |

---

## 14. เอกสารที่เกี่ยวข้อง
- **ต้นแบบแบบ interactive (ซีนหน้าเว็บ / หลังบ้าน, Union-Find ทีละขั้น, เครื่องคิด payout):** https://claude.ai/artifact/Ro3TSCAq5vLiGBx6usK15Z (เป็นแบบ private เจ้าของงานต้องเปิดหรือแชร์เอง) **หมายเหตุ:** เครื่องคิด payout ในนั้นยังเป็นแบบ FCFS ตัวเลขที่ถูกต้องคือข้อ 10.3
- **สไลด์ proposal วิชา DSA:** `C:\Users\MP2BD9BR\Downloads\for slide\AdCup_DSA_Proposal.pptx` หน้า 15–19 ใช้ตัวเลขแบบแบ่งตามสัดส่วนแล้ว ตรงกับข้อ 10.3
- **เนื้อหาสไลด์เดิม:** `linked-account-detection.md` **ล้าสมัย** (ตัวเลขยังเป็น FCFS) อย่าใช้เป็นแหล่งอ้างอิงตัวเลข
- **แหล่งอ้างอิงแนวทางในวงการ:** Google AdSense (one account per payee), Uber (fraud detection ด้วยกราฟของ device / payment ที่ใช้ร่วมกัน), SEON / Sift (multi-accounting ด้วย device และ IP), Whop (หน่วงการจ่ายเพื่อตรวจ)

"""
Hotel knowledge base embedded as a string for use as RAG context in agent system prompts.
All data sourced from das-elb-hotel/src/lib/rooms-data.ts and tagungen-data.ts.
"""

HOTEL_KNOWLEDGE_BASE = """
========================================================
DAS ELB HOTEL & RESTAURANT — OPERATIONS KNOWLEDGE BASE
========================================================

HOTEL PROFILE
-------------
Name:        Das ELB Hotel & Restaurant
Address:     Seilerweg 19, 39114 Magdeburg, Germany
Phone:       +49 391 756 326 60
Email:       rezeption@das-elb.de
Website:     https://www.das-elb-hotel.com
Total Rooms: 33 modern apartments
Location:    Stadtpark Rotehorn, on the Elbe riverbank, Magdeburg
Owner:       B. Singh Hotel GmbH & Co. KG (Bhupinder Singh)

OPERATING HOURS
---------------
Reception:   Daily 07:00 – 21:30
Restaurant:  12:00 – 22:00
Breakfast:   07:30 – 10:30
Check-in:    From 13:00 (early check-in on request, subject to availability)
Check-out:   Until 11:00 (late check-out on request, subject to availability)

SPECIAL FEATURES
----------------
- Panoramic Elbe river views from top-floor suites and balconies
- Located in Stadtpark Rotehorn — peaceful, nature surroundings
- Restaurant serving Indian and European cuisine
- Full conference and event facilities
- Free WiFi throughout
- On-site parking
- Wheelchair accessible
- Pets allowed

==========================
ROOM TYPES & PRICING
==========================

1. KOMFORT APARTMENT
   API key:    "komfort"
   Size:       40 m²
   Capacity:   2 persons
   Price:      from €89/night
   View:       Stadtpark Rotehorn
   Amenities:
     - Kingsize bed
     - Kitchenette
     - Smart TV
     - Free WiFi
     - Desk / workspace
     - Shower bathroom
     - Air conditioning

2. KOMFORT PLUS APARTMENT
   API key:    "komfort plus"
   Size:       45 m²
   Capacity:   2–3 persons
   Price:      from €119/night
   View:       Partial Elbe view, balcony
   Amenities:
     - Kingsize bed
     - Separate living area
     - Fully equipped kitchen
     - Smart TV
     - Free WiFi
     - Desk / workspace
     - Rain shower bathroom
     - Air conditioning
     - Balcony

3. SUITE DELUXE
   API key:    "suite"
   Size:       60 m²
   Capacity:   2–4 persons
   Price:      from €169/night
   View:       Panoramic Elbe view, panorama balcony
   Amenities:
     - Kingsize bed
     - Large living area
     - Fully equipped kitchen
     - 55" Smart TV
     - Free WiFi
     - Dedicated workspace
     - Luxury bathroom with bathtub
     - Air conditioning
     - Panorama balcony with Elbe view
     - Nespresso machine

==========================
CONFERENCE & MEETING ROOMS
==========================

1. VERANSTALTUNGS-/MEETINGRAUM (Main Event Room)
   API id:     "veranstaltungsraum"
   Capacity:   Up to 30 persons
   Price:      €400/day
   Features:   Full AV setup, flexible seating, natural light

2. WORKSHOP RAUM #405
   API id:     "workshop-405"
   Capacity:   Up to 14 persons
   Price:      €250/day
   Features:   Ideal for workshops, breakout sessions

==========================
CATERING PACKAGES (per person)
==========================

STARTER (Half-day)             — €59 per person
  Includes:
  - 1 morning coffee break (filter coffee, tea, seasonal fruit, biscuits)
  - Mineral water & soft drinks (0.2l) on tables throughout the day

STARTER PLUS (Full-day)        — €89 per person  ← MOST POPULAR
  Includes:
  - 1 morning coffee break
  - Mineral water & soft drinks on tables
  - 1 afternoon coffee break
  - Lunch buffet

KOMFORT (Full-day + Evening)   — €119 per person
  Includes:
  - 1 morning coffee break
  - Mineral water & soft drinks on tables
  - Lunch buffet
  - 1 afternoon coffee break
  - Dinner buffet

Dietary notes: Vegetarian, vegan, and allergen-specific requirements
accommodated on request — mention in booking.

==========================
EQUIPMENT RENTAL (per day)
==========================
Beamer & Screen (Leinwand):          €50
Flipcharts & Markers:                €15
Sound System (Beschallungsanlage):   €80
Video Conferencing System:           €100
Whiteboard:                          €10
Moderation Kit (Moderationskoffer):  €25

==========================
CANCELLATION POLICIES
==========================
Room Bookings:
  - Free cancellation until 24 hours before check-in
  - No-show or cancellation within 24h: full first night charged

Restaurant Reservations:
  - Free cancellation until 24 hours before reservation
  - No-show: invoice may be issued for reserved covers

Conference Bookings:
  - Cancellation terms communicated individually in the booking contract
  - Groups >10: special deposit and cancellation terms apply

==========================
PRICING EXAMPLES FOR COMMON REQUESTS
==========================
Example: 2-night stay, Suite Deluxe, 2 adults
  → 2 × €169 = €338 minimum (plus any extras)

Example: Full-day conference, 20 persons, Starter Plus catering, Beamer
  → Room: €400 + Catering: 20 × €89 + Beamer: €50 = €2,230

Example: Half-day workshop, 10 persons, Starter catering, Flipcharts
  → Room: €250 + Catering: 10 × €59 + Flipcharts: €15 = €855

==========================
UPSELL RULES (guide AI suggestions)
==========================
- Group stay >10 rooms        → Suggest banquet hall package + dedicated event manager
- Stay 4+ nights              → Mention "long-stay discount available on request"
- Business conference         → Upsell from Starter to Starter Plus catering
- Conference >20 persons      → Upsell Veranstaltungsraum if they inquired about Workshop Raum
- Suite Deluxe inquiry        → Mention panoramic Elbe view and Nespresso machine
- Honeymoon / anniversary     → Suggest Suite Deluxe + romantic decoration add-on
- Restaurant reservation 6+   → Suggest pre-ordering from the set menu

==========================
PAYMENT
==========================
Accepted: All major credit cards, cash, bank transfer
Invoices available for corporate clients

==========================
ACCESSIBILITY
==========================
Wheelchair accessible throughout public areas and selected rooms.
Notify in advance for accessible room allocation.

==========================
ESCALATION CONTACTS
==========================
Manager email:    manager@das-elb.de
Reception phone:  +49 391 756 326 60
Escalate when:
  - Complaint severity: high or critical
  - Group booking >10 rooms (requires manager sign-off)
  - Estimated revenue >€5,000 (single transaction)
  - Legal threats or refund disputes
  - VIP / press / media guests
  - Any no-show dispute over €500

==========================
CONTACT LANGUAGE GUIDE
==========================
German emails → Reply in formal German ("Sie" form, not "du")
  Sign-off:   "Mit freundlichen Grüßen,\nDas Team vom Das ELB Hotel & Restaurant"

English emails → Reply in professional, warm English
  Sign-off:   "Warm regards,\nThe Das ELB Team"

Mixed / uncertain → Default to German, add English translation below

Always include at the bottom of every reply:
  📍 Seilerweg 19, 39114 Magdeburg
  📞 +49 391 756 326 60
  ✉️  rezeption@das-elb.de
  🌐 www.das-elb-hotel.com
"""

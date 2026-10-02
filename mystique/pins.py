"""Drive files pinned to an association record or a developer delivery.

Markdown exports live in data/artifacts/site-docs. A file with no readable text
and no recorded title is not pinned one sheet at a time. Drafts, lender
envelopes, unit grant deeds, and third-party safety sheets are not pinned.
The document number in a pinned grant-deed filename is a fact. A recorder
search hit is not a fact until that file is pinned. Those numbers are enough
to run the chain again when the ownership database is gone.

Looked for on 2026-09-27 in Maps, Plans, Deeds, California BRE, Annexations,
and Governing Documents. Present: the final map, three condominium plans, the
common-area grant deeds, the annexations, the public reports, and the
construction drawings in John Laing Homes and Watt Communities. The three
subdividers are pinned on the community, not as extra files here. John Laing
Homes started the project. Mystique Builders sold units out of the bankruptcy.
Watt Communities at Mystique finished it. Absent: a notice of completion, a
completion bond, and a common-area warranty. The Phase
8 bond-release letter is in California BRE. It is the release, not the bond.
The Contracts library holds later vendor agreements. It is not the subdivider's
original contract file.
"""

from jason.community.documents import DocumentPin, PathPattern, deliver, pin
from jason.community.symbols import DeveloperDelivery, DocumentKind

FLOOD_POLICY = PathPattern("FLOOD POLICY {term} BLDG {building}.pdf")
USE_RULES = DeveloperDelivery.USE_RULES

PINS: tuple[DocumentPin, ...] = (
    pin("CCRs", "1hJcV7Vs2mu2IqMalANdsmE4gOA_RhgupNLwwXjHyfE8", DocumentKind.DECLARATION),
    pin("CCRs.pdf", "1bwNp97ksIRj9Li9KokZAK83yqm16oq15", DocumentKind.DECLARATION),
    pin("CCRs 200709120758.pdf", "1TOmCxykuMNRAlu9mRpQNhvdImj-oUjtY", DocumentKind.DECLARATION),
    pin("CCRs - 1st Amendment.pdf", "1yzsa5yPtb1L6NqdXs1vRU7cYrBBKT3jA", DocumentKind.AMENDMENT),
    pin("CCRs - 2nd Amendment", "1G2GgTJjpJ1N3ZFAT7XJ9K6NI5RrqP7FyM7SclFhdWRE", DocumentKind.AMENDMENT),
    pin("CCRs - 2nd Amendment.pdf", "10PpSqlRvKhEdJd7iBsBsZZN6iVWqp7-Z", DocumentKind.AMENDMENT),
    pin("CCRs - 3rd Amendment", "1Sz8Wq_4cOhkVj75lSc7wCXobUEs5LPsJm4zI2PkDBcQ", DocumentKind.AMENDMENT),
    pin("Bylaws", "1v9MqoGnOvEajRySi9sZJzB6SdaVJqfw4Tbi4ZB1JBFk", DocumentKind.BYLAWS),
    pin("Bylaws.pdf", "1D9P6xRgeQwaYPP2HLPrOkqNYzbO1fYQe", DocumentKind.BYLAWS),
    pin("Articles of Incorporation.pdf", "1Jj-Gx69FaP_7Jr1ywdhCR6kj8Qrti82Y", DocumentKind.ARTICLES),
    pin("Mystique - 221120 - Articles of Incorporation.pdf", "1J5nb5mhfKesudVz1CMzwW054jVgfz73U", DocumentKind.ARTICLES),
    pin("Election Rules", "1UuuNYH4OCjICBAQeTzV4WCzCWILTCILrSuR5v5o_oe4", DocumentKind.ELECTION_RULES),
    pin("Election Rules.pdf", "1I8pFw0R6AIq5UeYFVnP3O2Ar0LhMjNk1", DocumentKind.ELECTION_RULES),
    pin("Owner's Manual and Rules", "1cX1NqF21iVn2bSk8KF4l6MWKWxPqlqndgcAVJustRfo", DocumentKind.POLICY, delivery=USE_RULES),
    pin("Owner's Manual and Rules.pdf", "15xRNwgkoheL6R7JQXnHd2nmK0aOTy9OE", DocumentKind.POLICY, delivery=USE_RULES),
    pin("Enforcement Policy", "102vrT0lk2UDERTkQpSB776aGqKg9Gm4YCRjACcz80q0", DocumentKind.POLICY, delivery=USE_RULES),
    pin("ALPR Policy", "1tRv7GEG9WjJSBd71s1Yu3rgwTYgQWhcRbYZeSdmsiyI", DocumentKind.POLICY),
    pin("Assessment Collection Policy.pdf", "10mYguLcU7PgQ9iP_XZP3fcB-Y8N-A1kq", DocumentKind.POLICY),
    pin("Assessment Collection Policy.docx", "1EVxowpEHnfZkufUSiDWLTWynNeQGnhPY", DocumentKind.POLICY),
    pin("Ethics Policy.pdf", "1kbqS_Rmm2giSOGLLQadarbZi8eTD_pgF", DocumentKind.POLICY),
    pin("Fine Schedule.pdf", "1VUKqTtdAp-Hsq2sBIy1YXqapkKsacdda", DocumentKind.POLICY, delivery=USE_RULES),
    pin("Notice of Adopted Rule Change B-7, B-12, Fine Schedule.docx", "1LiqrKKg18ZVerUyyvhi6-ZtQ8m6S2_pm", DocumentKind.POLICY, delivery=USE_RULES),
    pin("Certificate of Insurance.pdf", "185K0_DzrvWBiLBLpFbUQnnDKNauSjttJ", DocumentKind.INSURANCE_POLICY),
    pin("FLOOD POLICY 26-27 BLDG 1.pdf", "15OZy5TL2DBqixw0A8oFRo1BQ4NHNNBoE", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 26-27 BLDG 2.pdf", "1iqzjMyKjR0V61wWi5fZPoQUP0ln2myTs", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 26-27 BLDG 7.pdf", "1R0ZpKaYvsmi7PPBCEGmf_71M_zPAdZ-6", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 3.pdf", "1bcLc8ZgQLo7y2jwsRU6TZnM43HIwV8rf", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 4.pdf", "1h6gM-KqoppI7ySPnA4BogeFY97BDt9bv", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 5.pdf", "1CiYtj6pl6O-vNLpghugnez1M3WkC2DOp", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 6.pdf", "1SIBGSNvIFDOdeu1xucsXjYZGgSukKYLl", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 7.pdf", "127dhaEjexHmf0XagFy1h4LZSEfUKOhUD", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("FLOOD POLICY 25-26 BLDG 8.pdf", "1KSiMMiE4-QIyqKoIKOzntDFA4SifxvIJ", DocumentKind.INSURANCE_POLICY, FLOOD_POLICY),
    pin("Annexation - Phase 2.pdf", "1gHRUr9BNaKD-LSxFjIgKcEk45EEaCvNY", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 3.pdf", "1nk-TT4-d02O7RfEjKiVAMR7zcZigsGgE", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 3 AMENDED.pdf", "1-VzXo_lkJLiMhaX1aaOKIJaBhrO0Zomj", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 4.pdf", "1IHKmrzCWewT1dqz1WbyXtwiCzD08E1hr", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 4 AMENDED.pdf", "1wgfVRp6dNbv3O7C4YNyyNWm997JhHwZa", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 5.pdf", "1NlcxYHc5I0Y9JkikFlyPpmjqR01ISmrZ", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 6.pdf", "1N82eD8VEAfW3q28jVo-tW535BvFeOeEY", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 7.pdf", "1s5vewgAoiNDwsbJ1qwhbHAAacr-5d9Bb", DocumentKind.ANNEXATION),
    pin("Annexation - Phase 8.pdf", "1neKkSpBNsauEGvy-ogUpcf4piLncdhyQ", DocumentKind.ANNEXATION),
    pin("Membership", "1LFwR2-_RX8h9_o3EwMd_P5R8h3q4Jtl3J12KzoeG_4I", DocumentKind.MEMBERSHIP_LIST),
    deliver("Final Map of JMA North Natomas Parcel 4.pdf", "11IhSBrnVvHvVKB7SpqEVJCFjm2gFvIhY", DocumentKind.MAP, DeveloperDelivery.SUBDIVISION_MAP),
    deliver("Condominium Plan 200709120757.PDF", "1-UM5eDnVjE927hq4-BKWRWOGjOfkre4B", DocumentKind.CONDOMINIUM_PLAN, DeveloperDelivery.CONDOMINIUM_PLAN),
    deliver("Condominium Plan 201809211358.pdf", "1xMtkt6r-bS8sgC6Ljkju5MD8QsdYLUjD", DocumentKind.CONDOMINIUM_PLAN, DeveloperDelivery.CONDOMINIUM_PLAN),
    deliver("Condominium Plan Mystique 201901161002.pdf", "1beCGX0fZnLe-0bW9buN-Qz_hT3vtcaii", DocumentKind.CONDOMINIUM_PLAN, DeveloperDelivery.CONDOMINIUM_PLAN),
    deliver("GD 200605041076.pdf", "1V6p-Sw8j_DGhJK6o42qtpiWmKuJlt_2W", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 200709281731.PDF", "1pwq7cXEHRGdCuZwPzVwmZw4OwUd2v-r0", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 200709281731.pdf", "1YMenG2gzuChsSsqTc7GosHYT_Jupb0q9", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 200805280293.PDF", "1V_GtbH4WBpJ_xz2FktoDCwonjTTWmXA6", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201010121565.pdf", "1PmkEC7M5fUY5E90RHYcrrWEWLABeqDv5", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201010121566.PDF", "17BzdFwO7uMh_iMgfhB72ebFKXKfiJC_O", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201102010742.PDF", "1p_Jbzj62EVKnO_egwUrersYrC4zHyJS0", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201103180727.pdf", "1z7gmmGxSkO8XE_aZ9nrYi60Y_SLVakWc", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201103251102.pdf", "1N9rV-ss3LX_lE15lxTrwCsf1Acl5RN8z", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201209211820.pdf", "1NsCEBP5dmOEwHM5hXjg8TnAvucRGiQy0", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201310300906.pdf", "1iWBwZ2OBd6PiubZ0db_m0dRQgDzm5OJz", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201604280702.pdf", "1I3rBXVS_l-wBSfWLkee-s4gqDHPurwB1", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201703240140.pdf", "1ZGP2yUJYMW-VRnif4chBZ_KLT6yU1V8D", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 201907100675.pdf", "1VtrfV1xP4NDN1U0mMK9_EFmmYee1XsaB", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202002281258 - Phase 3.pdf", "1cKXmVF3Vd3p3ruBAKm7lJMm-3J47NrSG", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202005131114 - Phase 5.pdf", "1SERFQbatp12FTJpw7KGLhMV4oB90Tuor", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202008191298 - Phase 6.pdf", "1oyNuz6Kjco5PZ6OSOHbJIRaT_GQjFsM0", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202011041576.pdf", "1K__U2HMW71WBW88L7m-pY2LmRE0BXMYQ", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202104282025 - Phase 7.pdf", "1vXj8xna3AHr_vwuuyvP62U4HdCeYOrue", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202203180703 - Phase 4.pdf", "1ehUYZdo2efW2l7whA1orzKwf6AjFmiGa", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("GD 202203180704 - Phase 8.pdf", "1rvreJJhnODMrWzIWkSi3jw9i7AMd65fR", DocumentKind.GRANT_DEED, DeveloperDelivery.COMMON_AREA_DEED),
    deliver("John Laing Homes", "1Ta98-Ekr2-Tf-Cbd1_Y_akgT0CFURUfW", DocumentKind.PLAN_SET, DeveloperDelivery.MAINTENANCE_PLANS),
    deliver("Watt Communities (New Buildings)", "17ohMjY8-KrTSPbKY4DpJEBOw3pFnguY2", DocumentKind.PLAN_SET, DeveloperDelivery.MAINTENANCE_PLANS),
    deliver("DR18-052_APP.pdf", "1Apc7ytRA3Vxv4WyJRvxcdfetz29AB2Gt", DocumentKind.PLAN_SET, DeveloperDelivery.MAINTENANCE_PLANS),
    deliver("DR18-052_PLANS.pdf", "1c3yAsMrL4qyhzeY13GihHdXPRJDeai3w", DocumentKind.PLAN_SET, DeveloperDelivery.MAINTENANCE_PLANS),
    deliver("DR18-052_ROD.pdf", "1fFh5AN0VDzRM1oyi_kyTSuQgUy7-e8AV", DocumentKind.PLAN_SET, DeveloperDelivery.MAINTENANCE_PLANS),
    deliver("130654SA-F00_2.PDF", "1C6cbeD1h5brKdaMlPsYd2Ouz2cOJi6hg", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("132246SA-F00.PDF", "1bEGv4a2EKbsxJQY_lIr3ICVPhnnI8qDc", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("154410SA-A01.pdf", "1GP931lG6y7RuCz8yLgWPfRtnl4-NHt7D", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("160779SA-A01.pdf", "1v42advYYJi4TGpZ4jDhCEHSfLqQLKLI0", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("160779SA-F00.pdf", "1MLnTZGbg8x4NFE0CHLfCHERAdfRUu7-z", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("163389SA-F00.pdf", "1nw17gcMc2FIV3nRmAM5DSe1QShgE40QS", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("163389SA-F00C00.pdf", "1kDi-hxcic7xG0LkSiXDI0m9-bpe1hG84", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("163389SA-S00.pdf", "1x9_Ehg9UgTB5PtUuYSND0kFVSuUgINLd", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("164002SA-F00.pdf", "1q7TrLUE_A5ONIw06pu14MMIdEHdMS6VG", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("165814SA-F00.pdf", "1H6dsa0SlpsUufZVT-LqrU79OA1JUIQRk", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
    deliver("165817SA-F00.pdf", "1SFWuWRTxTXTssP3AKhlNU5AjbjdUU-Wq", DocumentKind.DRE_REPORT, DeveloperDelivery.PUBLIC_REPORT),
)

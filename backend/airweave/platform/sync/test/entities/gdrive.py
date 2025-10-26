"""Real Google Drive entities captured from actual sync for testing."""

from datetime import datetime, timezone

from airweave.platform.entities.google_drive import (
    GoogleDriveDriveEntity,
    GoogleDriveFileEntity,
)

# Drive entity (shared drive)
drive = GoogleDriveDriveEntity(
    entity_id="0AI9wULv34ENVUk9PVA",
    breadcrumbs=[],
    name="Airweave",
    created_at=None,
    updated_at=None,
    kind="drive#drive",
    color_rgb=None,
    hidden=False,
    org_unit_id=None,
)

# File entities - one densest example per file type

# 1. TEXT FILE - Dec Feedback Eline.txt (3,040 bytes)
text_file = GoogleDriveFileEntity(
    entity_id="1DL-7GT1PESJf4LU3-xm82_u9KNwGk2e5",
    breadcrumbs=[],
    name="Dec Feedback Eline.txt",
    created_at=datetime(2025, 4, 14, 19, 15, 0, 727000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 4, 14, 19, 37, 11, 984000, tzinfo=timezone.utc),
    url=("https://www.googleapis.com/drive/v3/files/1DL-7GT1PESJf4LU3-xm82_u9KNwGk2e5?alt=media"),
    size=3040,
    file_type="text",
    mime_type="text/plain",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Dec Feedback Eline.txt"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1NfOHfSvA-hl-lk-FvwREVPuMnvTIDVWk"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1DL-7GT1PESJf4LU3-xm82_u9KNwGk2e5/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/text/plain",
    md5_checksum="8c1450e8842e442e4199f742339f23e3",
)

# 2. PDF FILE - DDIA.pdf (24,975,901 bytes - THE DENSEST PDF)
pdf_file = GoogleDriveFileEntity(
    entity_id="17llNMF7EhkVXQlKFLzEgQOv6M7iiB9yR",
    breadcrumbs=[],
    name="DDIA.pdf",
    created_at=datetime(2025, 4, 14, 19, 16, 7, 90000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 4, 14, 19, 32, 21, 472000, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/17llNMF7EhkVXQlKFLzEgQOv6M7iiB9yR?alt=media",
    size=24975901,
    file_type="pdf",
    mime_type="application/pdf",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "DDIA.pdf"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1OgWmtri077gBHYrQcf7fd7jtiFV57IUj"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/17llNMF7EhkVXQlKFLzEgQOv6M7iiB9yR/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/application/pdf",
    md5_checksum="bf7c3fecfe5dcffceb170b2aa6d34c31",
)

# 2a. PDF FILE - Amazon 2024 Annual Report (1,314,791 bytes)
amazon_2024_pdf = GoogleDriveFileEntity(
    entity_id="1AMZN2024AnnualReportXYZ123456",
    breadcrumbs=[],
    name="Amazon-2024-Annual-Report.pdf",
    created_at=datetime(2025, 10, 23, 10, 11, 0, tzinfo=timezone.utc),
    updated_at=datetime(2025, 10, 23, 10, 11, 0, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1AMZN2024AnnualReportXYZ123456?alt=media",
    size=1314791,
    file_type="pdf",
    mime_type="application/pdf",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Amazon-2024-Annual-Report.pdf"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1TestFolderAmazonReports"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1AMZN2024AnnualReportXYZ123456/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/application/pdf",
    md5_checksum="amazon2024test123",
)

# 2b. PDF FILE - Amazon 2023 Annual Report (1,314,396 bytes)
amazon_2023_pdf = GoogleDriveFileEntity(
    entity_id="1AMZN2023AnnualReportABC789012",
    breadcrumbs=[],
    name="Amazon-com-Inc-2023-Annual-Report.pdf",
    created_at=datetime(2024, 10, 23, 10, 11, 0, tzinfo=timezone.utc),
    updated_at=datetime(2024, 10, 23, 10, 11, 0, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1AMZN2023AnnualReportABC789012?alt=media",
    size=1314396,
    file_type="pdf",
    mime_type="application/pdf",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Amazon-com-Inc-2023-Annual-Report.pdf"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1TestFolderAmazonReports"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1AMZN2023AnnualReportABC789012/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/application/pdf",
    md5_checksum="amazon2023test789",
)

# 3. WORD DOC - Tips and tops (received).docx (277,633 bytes)
word_file = GoogleDriveFileEntity(
    entity_id="1RLc4U7VmayjFRXzkAmO8QmS6_dK_nSbS",
    breadcrumbs=[],
    name="Tips and tops (received).docx",
    created_at=datetime(2025, 4, 14, 19, 14, 56, 741000, tzinfo=timezone.utc),
    updated_at=datetime(2025, 4, 14, 19, 37, 8, 461000, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1RLc4U7VmayjFRXzkAmO8QmS6_dK_nSbS?alt=media",
    size=277633,
    file_type="microsoft_word_doc",
    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Tips and tops (received).docx"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1LW1_p-8i9-XX0c1krFKOr72Cc1sVq13r"],
    owners=[],
    shared=False,
    web_view_link=(
        "https://docs.google.com/document/d/1RLc4U7VmayjFRXzkAmO8QmS6_dK_nSbS/"
        "edit?usp=drivesdk&ouid=112956215928753068891&rtpof=true&sd=true"
    ),
    icon_link=(
        "https://drive-thirdparty.googleusercontent.com/16/type/"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    md5_checksum="fe7237b1ec81c407c7529464a016a9e8",
)

# 4. POWERPOINT - Rewire Compentency Model V0.9.pptx (1,709,372 bytes)
pptx_file = GoogleDriveFileEntity(
    entity_id="1cVeMTkBt3z6a-u3srW8Svh83hm6nky3o",
    breadcrumbs=[],
    name="Rewire Compentency Model V0.9.pptx",
    created_at=datetime(2025, 4, 14, 19, 14, 56, 67000, tzinfo=timezone.utc),
    updated_at=datetime(2024, 11, 12, 11, 41, 10, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1cVeMTkBt3z6a-u3srW8Svh83hm6nky3o?alt=media",
    size=1709372,
    file_type="microsoft_powerpoint",
    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Rewire Compentency Model V0.9.pptx"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1LW1_p-8i9-XX0c1krFKOr72Cc1sVq13r"],
    owners=[],
    shared=False,
    web_view_link=(
        "https://docs.google.com/presentation/d/1cVeMTkBt3z6a-u3srW8Svh83hm6nky3o/"
        "edit?usp=drivesdk&ouid=112956215928753068891&rtpof=true&sd=true"
    ),
    icon_link=(
        "https://drive-thirdparty.googleusercontent.com/16/type/"
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    md5_checksum="9361ea53af7d7e223e2869bef7c7bae5",
)

# 5. EXCEL - Voorlopige analyse verkoop Cuyp 2.0.xlsx (10,181 bytes)
excel_file = GoogleDriveFileEntity(
    entity_id="1mPd-clWJGBFSsdoSqS39-BO69ZmpqXAl",
    breadcrumbs=[],
    name="Voorlopige analyse verkoop Cuyp 2.0.xlsx",
    created_at=datetime(2025, 4, 14, 19, 15, 39, 898000, tzinfo=timezone.utc),
    updated_at=datetime(2024, 11, 26, 14, 6, 24, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1mPd-clWJGBFSsdoSqS39-BO69ZmpqXAl?alt=media",
    size=10181,
    file_type="microsoft_excel",
    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "Voorlopige analyse verkoop Cuyp 2.0.xlsx"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1OgVQKMmuYmVDjds5ypm2hv-4gBZgHMOH"],
    owners=[],
    shared=False,
    web_view_link=(
        "https://docs.google.com/spreadsheets/d/1mPd-clWJGBFSsdoSqS39-BO69ZmpqXAl/"
        "edit?usp=drivesdk&ouid=112956215928753068891&rtpof=true&sd=true"
    ),
    icon_link=(
        "https://drive-thirdparty.googleusercontent.com/16/type/"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ),
    md5_checksum="1b2f3c6c6c9521fd577e1d908f95a5d5",
)

# 6. JPEG IMAGE - IMG_3962 JH.jpg (2,176,663 bytes)
jpeg_file = GoogleDriveFileEntity(
    entity_id="1RFi3qjfe_cNgOCjADQLunp7WxnI-Ml5N",
    breadcrumbs=[],
    name="IMG_3962 JH.jpg",
    created_at=datetime(2025, 4, 14, 19, 15, 46, 199000, tzinfo=timezone.utc),
    updated_at=datetime(2021, 10, 6, 9, 12, 42, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1RFi3qjfe_cNgOCjADQLunp7WxnI-Ml5N?alt=media",
    size=2176663,
    file_type="image_jpeg",
    mime_type="image/jpeg",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "IMG_3962 JH.jpg"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1_uHJIiInvfIYYiBXFcHOrc2yZinbgVrU"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1RFi3qjfe_cNgOCjADQLunp7WxnI-Ml5N/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/image/jpeg",
    md5_checksum="6dd86695a6265034d4b52f2ed904622a",
)

# 7. APPLE PAGES - MICompany Cover Letter.pages (890,183 bytes)
pages_file = GoogleDriveFileEntity(
    entity_id="1YRJdlhkK06cBBvl3TUW3tnuBPwtvCezZ",
    breadcrumbs=[],
    name="MICompany Cover Letter.pages",
    created_at=datetime(2024, 11, 21, 19, 31, 41, 297000, tzinfo=timezone.utc),
    updated_at=datetime(2023, 9, 4, 14, 58, 9, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1YRJdlhkK06cBBvl3TUW3tnuBPwtvCezZ?alt=media",
    size=890183,
    file_type="application",
    mime_type="application/x-iwork-pages-sffpages",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "MICompany Cover Letter.pages"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1-VvJ8dOojH9jWNdGchCnEEVRD68l966H"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1YRJdlhkK06cBBvl3TUW3tnuBPwtvCezZ/view?usp=drivesdk",
    icon_link=(
        "https://drive-thirdparty.googleusercontent.com/16/type/application/x-iwork-pages-sffpages"
    ),
    md5_checksum="3790b2cbef6cdace765d083edbe91c81",
)

# 8. ZIP FILE - paspoorten verkopers[10].zip (4,109,927 bytes)
zip_file = GoogleDriveFileEntity(
    entity_id="1PlNN988XRfVAVR3LRdRUSwatlNLPJ0ZQ",
    breadcrumbs=[],
    name="paspoorten verkopers[10].zip",
    created_at=datetime(2025, 4, 14, 19, 15, 38, 201000, tzinfo=timezone.utc),
    updated_at=datetime(2024, 12, 5, 9, 55, 52, tzinfo=timezone.utc),
    url="https://www.googleapis.com/drive/v3/files/1PlNN988XRfVAVR3LRdRUSwatlNLPJ0ZQ?alt=media",
    size=4109927,
    file_type="zip",
    mime_type="application/zip",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "paspoorten verkopers[10].zip"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["12q7JyA9CVQtbcWYaeUdPRfSLySRR1iIG"],
    owners=[],
    shared=False,
    web_view_link="https://drive.google.com/file/d/1PlNN988XRfVAVR3LRdRUSwatlNLPJ0ZQ/view?usp=drivesdk",
    icon_link="https://drive-thirdparty.googleusercontent.com/16/type/application/zip",
    md5_checksum="07c80bd7bb1247156c90cf32a81e0cc0",
)

# 9. GOOGLE DOC (exported as DOCX) - CV.docx (4,841 bytes)
google_doc_file = GoogleDriveFileEntity(
    entity_id="11RT_yhZcoWX6nOX5hLBXH7kCOtbRMErXghGR9rlpdwA",
    breadcrumbs=[],
    name="CV.docx",
    created_at=datetime(2024, 11, 21, 19, 41, 49, 717000, tzinfo=timezone.utc),
    updated_at=datetime(2024, 11, 21, 19, 41, 53, 539000, tzinfo=timezone.utc),
    url=(
        "https://www.googleapis.com/drive/v3/files/"
        "11RT_yhZcoWX6nOX5hLBXH7kCOtbRMErXghGR9rlpdwA/export?"
        "mimeType=application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    size=4841,
    file_type="google_doc",
    mime_type="application/vnd.google-apps.document",
    local_path=(
        "/Users/daanmanneke/Desktop/airweave/backend/airweave/platform/sync/test/entities/tmp/"
        "CV.docx"
    ),
    description=None,
    starred=False,
    trashed=False,
    explicitly_trashed=False,
    parents=["1y9koL2REnMwzCzlQfus3J96meubbyZiR"],
    owners=[],
    shared=False,
    web_view_link=(
        "https://docs.google.com/document/d/11RT_yhZcoWX6nOX5hLBXH7kCOtbRMErXghGR9rlpdwA/"
        "edit?usp=drivesdk"
    ),
    icon_link=(
        "https://drive-thirdparty.googleusercontent.com/16/type/"
        "application/vnd.google-apps.document"
    ),
    md5_checksum=None,
)

# Amazon PDFs for testing textual representations
amazon_pdf_examples = [
    amazon_2024_pdf,
    amazon_2023_pdf,
]

# All entities in one list (1 drive + multiple file types)
gdrive_examples = [
    drive,
    text_file,
    pdf_file,
    word_file,
    pptx_file,
    excel_file,
    jpeg_file,
    pages_file,
    zip_file,
    google_doc_file,
    amazon_2024_pdf,
    amazon_2023_pdf,
]

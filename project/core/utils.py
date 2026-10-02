
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from datetime import datetime

def generate_loyalty_transfer_excel(transfers, transfer_type='single'):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "النقاط"
    
    headers = ['رقم العضوية', 'اسم العميل', 'النقاط المحولة','الفرع','تاريخ التحويل']
    header_fill = PatternFill(start_color="2563eb", end_color="2563eb", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row, transfer in enumerate(transfers, 2):
        ws.cell(row=row, column=1, value=transfer.customer.customer_id if transfer.customer else '-')
        ws.cell(row=row, column=2, value=transfer.customer.full_name if transfer.customer else '-')
        ws.cell(row=row, column=3, value=transfer.points)
        ws.cell(row=row, column=4, value=transfer.branch.name if transfer.branch else '-')
        ws.cell(row=row, column=5, value=transfer.transfer_date.strftime('%Y-%m-%d %H:%M') if transfer.transfer_date else datetime.now().strftime('%Y-%m-%d %H:%M'))
        
        for col in range(1, 6):
            ws.cell(row=row, column=col).border = border
            ws.cell(row=row, column=col).alignment = Alignment(horizontal='center')
    
    for col in range(1, 6):
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    return wb


def create_excel_response(wb, filename):
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


from decimal import Decimal

from .models import Product, Category


DXN_PRODUCTS = {
    "ريشي آر جي 90 كبسولة": {
        "category": "المكملات الغذائية",
        "pv": 51.5,
        "selling_price": 480,
    },
    "ريشي جي إل 90 كبسولة": {
        "category": "المكملات الغذائية",
        "pv": 36.5,
        "selling_price": 340,
    },
    "ريشيمليوم بودر 70 جرام": {
        "category": "المكملات الغذائية",
        "pv": 92,
        "selling_price": 895,
    },
    "ريشيمليوم بودر 22 جرام": {
        "category": "المكملات الغذائية",
        "pv": 29,
        "selling_price": 275,
    },
    "لقاح النحل 120 قرص": {
        "category": "المكملات الغذائية",
        "pv": 21,
        "selling_price": 235,
    },
    "كورديسيبس 120 قرص": {
        "category": "المكملات الغذائية",
        "pv": 85,
        "selling_price": 840,
    },
    "سبيرولينا 120 قرص": {
        "category": "المكملات الغذائية",
        "pv": 20,
        "selling_price": 230,
    },
    "سبيرولينا 500 قرص": {
        "category": "المكملات الغذائية",
        "pv": 75,
        "selling_price": 750,
    },
    "عرف الأسد 120 قرص": {
        "category": "المكملات الغذائية",
        "pv": 33,
        "selling_price": 380,
    },
    "عرف الأسد بودر 30ج": {
        "category": "المكملات الغذائية",
        "pv": 27.5,
        "selling_price": 315,
    },
    "كورديسيبس بودر 30جرام": {
        "category": "المكملات الغذائية",
        "pv": 47.5,
        "selling_price": 465,
    },
    "بوتنزي 30 كبسولة": {
        "category": "المكملات الغذائية",
        "pv": 25.5,
        "selling_price": 280,
    },
    "ميكوفجي 200 جرام": {
        "category": "المكملات الغذائية",
        "pv": 53,
        "selling_price": 510,
    },
    "ميكوفجي 400 جرام": {
        "category": "المكملات الغذائية",
        "pv": 95,
        "selling_price": 900,
    },
    "ميكوفجيا (ظرف وزن 12 جرام)": {
        "category": "المكملات الغذائية",
        "pv": 14.8,
        "selling_price": 145,
    },
    "شراب الكحة": {
        "category": "المكملات الغذائية",
        "pv": 13.5,
        "selling_price": 140,
    },
    "ميكوفجيا (ظرف وزن 24 جرام)": {
        "category": "المكملات الغذائية",
        "pv": 27,
        "selling_price": 255,
    },
    "بودرة اللؤلؤ 30 جرام": {
        "category": "المكملات الغذائية",
        "pv": 26,
        "selling_price": 270,
    },

    "عصير مورينزي 285ml": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 16,
        "selling_price": 180,
    },
    "قهوة سوداء بدون سكر": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 11,
        "selling_price": 125,
    },
    "قهوة لينجزي 3*1": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 9.5,
        "selling_price": 110,
    },
    "قهوة لينجزي 3*1 لايت": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 9.5,
        "selling_price": 110,
    },
    "قهوة فيتا كوفي 1*6": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 12,
        "selling_price": 130,
    },
    "قهوة عرف الأسد": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 12.5,
        "selling_price": 135,
    },
    "قهوة كورديسيبس 3*1": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 10.5,
        "selling_price": 115,
    },
    "قهوة بيضاء": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 10.5,
        "selling_price": 115,
    },
    "شاي مع القهوة": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 11,
        "selling_price": 120,
    },
    "كوكوزي": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 9,
        "selling_price": 170,
    },
    "ليمونزي": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 7,
        "selling_price": 80,
    },
    "ملح جبال الهيمالايا": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 4.8,
        "selling_price": 65,
    },
    "حلوى نعناع بلس ظرف": {
        "category": "المنتجات الغذائية والمشروبات",
        "pv": 1.7,
        "selling_price": 25,
    },

    "معجون كبير عادي 150ج": {
        "category": "منتجات العناية الشخصية",
        "pv": 6.3,
        "selling_price": 85,
    },
    "معجون كبير بلس 150ج": {
        "category": "منتجات العناية الشخصية",
        "pv": 7.1,
        "selling_price": 85,
    },
    "معجون أسنان صغير 75ج": {
        "category": "منتجات العناية الشخصية",
        "pv": 4,
        "selling_price": 50,
    },
    "شامبو جانوزي 250مل": {
        "category": "منتجات العناية الشخصية",
        "pv": 12,
        "selling_price": 115,
    },
    "شامبو جانوزي بلس 250مل": {
        "category": "منتجات العناية الشخصية",
        "pv": 13.2,
        "selling_price": 125,
    },
    "رغوة جسم 250مل": {
        "category": "منتجات العناية الشخصية",
        "pv": 12,
        "selling_price": 115,
    },
    "صابون جانوزي": {
        "category": "منتجات العناية الشخصية",
        "pv": 3.5,
        "selling_price": 45,
    },
    "كريم شجرة الشاي": {
        "category": "منتجات العناية الشخصية",
        "pv": 5.1,
        "selling_price": 65,
    },
    "مرهم زي ميكو": {
        "category": "منتجات العناية الشخصية",
        "pv": 3.8,
        "selling_price": 60,
    },
    "زيت جانوز": {
        "category": "منتجات العناية الشخصية",
        "pv": 10.5,
        "selling_price": 110,
    },
    "زيت أطفال تشوبي 200مل": {
        "category": "منتجات العناية الشخصية",
        "pv": 3.8,
        "selling_price": 55,
    },
    "زيت جوز الهند مع الجانوديرما-285مل": {
        "category": "منتجات العناية الشخصية",
        "pv": 17,
        "selling_price": 220,
    },
    "بودرة التلكوم": {
        "category": "منتجات العناية الشخصية",
        "pv": 4.5,
        "selling_price": 65,
    },
    "أحمر الشفاه": {
        "category": "منتجات العناية الشخصية",
        "pv": 11.2,
        "selling_price": 95,
    },
    "كريم التطهير جانوزي E": {
        "category": "منتجات العناية الشخصية",
        "pv": 29.6,
        "selling_price": 225,
    },
    "كريم ليل جانوزي E": {
        "category": "منتجات العناية الشخصية",
        "pv": 43.5,
        "selling_price": 300,
    },
    "واقي شمس جانوزي E": {
        "category": "منتجات العناية الشخصية",
        "pv": 40.6,
        "selling_price": 280,
    },
    "مجموعة جانوزي الصغيرة للسفر": {
        "category": "منتجات العناية الشخصية",
        "pv": 26,
        "selling_price": 230,
    },
    "مقشر بابايا بالجانوديرما": {
        "category": "منتجات العناية الشخصية",
        "pv": 7.1,
        "selling_price": 100,
    },
    "ألوفيرا / كريم ليلي": {
        "category": "منتجات العناية الشخصية",
        "pv": 7.1,
        "selling_price": 80,
    },
    "ألوفيرا / مرطب نهاري": {
        "category": "منتجات العناية الشخصية",
        "pv": 11,
        "selling_price": 120,
    },
    "ألوفيرا / لوشن لجسم واليد": {
        "category": "منتجات العناية الشخصية",
        "pv": 3.8,
        "selling_price": 60,
    },
    "ألوفيرا / مقشر بشرة": {
        "category": "منتجات العناية الشخصية",
        "pv": 5.7,
        "selling_price": 70,
    },
    "ألوفيرا / قناع": {
        "category": "منتجات العناية الشخصية",
        "pv": 7.4,
        "selling_price": 90,
    },
    "ألوفيرا / تونر مرطب": {
        "category": "منتجات العناية الشخصية",
        "pv": 5.2,
        "selling_price": 70,
    },
    "ألوفيرا / غسول": {
        "category": "منتجات العناية الشخصية",
        "pv": 4.2,
        "selling_price": 65,
    },
}


def import_dxn_products():

    created_count = 0
    updated_count = 0

    for name, data in DXN_PRODUCTS.items():

        category, _ = Category.objects.get_or_create(
            name=data["category"]
        )

        product, created = Product.objects.update_or_create(
            name=name,
            defaults={
                "category": category,
                "cost_price": Decimal(str(data["selling_price"])),
                "selling_price": Decimal(str(data["selling_price"])),
                "loyalty_points": Decimal(str(data["pv"])),
                "is_active": True,
            }
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count
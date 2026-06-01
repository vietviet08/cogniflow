import sys
import os
import json
import uuid

# Đảm bảo thư mục api nằm trong python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.storage.db import SessionLocal
from app.storage.models import Report
from app.services.evaluation_service import evaluate_report_quality

def run_evaluation():
    db = SessionLocal()
    print("="*70)
    print("      BẮT ĐẦU KIỂM THỬ ĐÁNH GIÁ CHẤT LƯỢNG TRUY VẤN RAG (NOTEMESH)")
    print("="*70)
    
    try:
        # Lấy báo cáo mới nhất trong cơ sở dữ liệu
        latest_report = db.query(Report).order_by(Report.created_at.desc()).first()
        
        if not latest_report:
            print("[LƯU Ý] Không tìm thấy báo cáo (Report) nào trong cơ sở dữ liệu Postgres.")
            print(" -> Hãy chắc chắn bạn đã chạy Web UI (Next.js), tải tài liệu lên và ấn nút 'Generate Report' hoặc 'Tạo báo cáo'.")
            print(" -> Hoặc bạn có thể chạy file 'api/scripts/seed_demo.py' để nạp dữ liệu mẫu trước.")
            return
            
        print(f"[*] Tìm thấy Báo cáo mới nhất:")
        print(f"    - ID: {latest_report.id}")
        print(f"    - Tiêu đề: {latest_report.title}")
        print(f"    - Yêu cầu truy vấn: {latest_report.query}")
        print(f"    - Loại báo cáo: {latest_report.report_type}")
        print("-" * 70)
        print("[*] Đang tính toán các chỉ số chất lượng RAG...")
        
        # Chạy service đánh giá chất lượng
        result = evaluate_report_quality(db, latest_report.id)
        
        if not result:
            print("[!] Không thể đánh giá báo cáo này.")
            return
            
        print("\n" + "="*25 + " KẾT QUẢ ĐÁNH GIÁ CHI TIẾT " + "="*25)
        print(f"Trạng thái đánh giá chung (Status) : {result['status'].upper()}")
        print(f"Điểm tổng hợp RAG (Overall Score) : {result['overall_score']} / 100")
        print("-" * 70)
        
        print("1. Điểm số các tiêu chí thành phần (từ 0.0 đến 1.0):")
        for key, val in result["scores"].items():
            print(f"   - {key.replace('_', ' ').title():<25}: {val:.3f}")
            
        print("\n2. Số liệu thống kê chi tiết:")
        for key, val in result["metrics"].items():
            print(f"   - {key.replace('_', ' ').title():<25}: {val}")
            
        print("\n3. Chi tiết các hạng mục kiểm thử (Checks):")
        for idx, check in enumerate(result["checks"], 1):
            print(f"   [{idx}] {check['label']}")
            print(f"       + Trạng thái: {check['status'].upper()}")
            print(f"       + Điểm số   : {check['score']:.3f}")
            print(f"       + Chi tiết  : {check['detail']}")
            
        if result["recommendations"]:
            print("\n4. Đề xuất cải thiện (Recommendations):")
            for rec in result["recommendations"]:
                print(f"   - {rec}")
        print("="*70)
        
    except Exception as e:
        print(f"[!] Đã xảy ra lỗi khi chạy đánh giá: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_evaluation()

from datetime import datetime
import pytz


def get_current_time_info():
    """
    Trả về thông tin thời gian hiện tại ở Thành phố Hồ Chí Minh.
    """
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    now = datetime.now(tz)
    day_name = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật'][now.weekday()]
    current_time = now.strftime("%H:%M (GMT+7), %d/%m/%Y")
    time_string = f"Hiện tại là {current_time}, {day_name}. **(bạn không cần nhắc lại phần này)** "
    return time_string

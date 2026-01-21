let violationCount = 0;

window.addEventListener('blur', () => {
    violationCount++;
    if (violationCount >= 3) {
        alert("BẠN ĐÃ VI PHẠM 3 LẦN. HỆ THỐNG TỰ ĐỘNG NỘP BÀI!");
        document.getElementById('exam-form').submit(); [cite: 63]
    } else {
        alert(`CẢNH BÁO: Không chuyển tab/thoát màn hình! (Lần ${violationCount}/3)`); [cite: 62]
    }
});

// Vô hiệu hóa chuột phải và các phím tắt copy/paste
document.addEventListener('contextmenu', e => e.preventDefault());
document.addEventListener('keydown', e => {
    if (e.ctrlKey && (e.key === 'c' || e.key === 'v')) {
        e.preventDefault();
        alert("Hành động bị cấm!");
    }
});
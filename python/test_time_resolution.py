from datetime import time

def resolve_time_for_shift(shift: str, time_group: str) -> time:
    group = (time_group or "").strip()
    if group == "Sau ăn giữa ca":
        if shift == "shift_1":
            return time(11, 30)
        elif shift == "shift_2":
            return time(19, 0)
        elif shift == "shift_3":
            return time(3, 0)
        else: # administrative
            return time(13, 0)
    elif group == "Cuối ca":
        if shift == "shift_1":
            return time(13, 0)
        elif shift == "shift_2":
            return time(21, 0)
        elif shift == "shift_3":
            return time(5, 0)
        else: # administrative
            return time(16, 0)
            
    lines = [line.strip("() \n\r") for line in group.split("\n") if line.strip()]
    if len(lines) == 4:
        idx = {
            "shift_1": 0,
            "administrative": 1,
            "shift_2": 2,
            "shift_3": 3,
        }.get(shift, 1)
        val = lines[idx]
        try:
            h, m = map(int, val.split(":"))
            if shift == "shift_1" and h == 1:
                h = 13
            return time(h, m)
        except Exception:
            pass
            
    return time(0, 0)

# Let's test the 9 time groups in TL.DTL.1.xls
time_groups = [
    '6:00\n(8:20)\n(14:00)\n(22:00)',
    '7:00\n(9:20)\n(15:00)\n(23:00)',
    '8:00\n(10:00)\n(16:00)\n(00:00)',
    '9:00\n(11:00)\n(17:00)\n(1:00)',
    '11:00\n(13:00)\n(19:00)\n(3:00)',
    'Sau ăn giữa ca',
    '12:00\n(15:00)\n(20:00)\n(4:00)',
    '1:00\n(16:00)\n(21:00)\n(5:00)',
    'Cuối ca'
]

shifts = ["administrative", "shift_1", "shift_2", "shift_3"]

for sh in shifts:
    resolved_times = [resolve_time_for_shift(sh, tg).strftime("%H:%M") for tg in time_groups]
    print(f"Shift {sh:<15}: {resolved_times}")

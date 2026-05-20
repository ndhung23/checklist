[Sơ đồ tổ chức.xlsx](https://github.com/user-attachments/files/28044624/S.d.t.ch.c.xlsx)
[SV・DSVの巡回チェックシート.xls](https://github.com/user-attachments/files/28044623/SV.DSV.xls)
[TL・DTLの巡回チェックシート 1.xls](https://github.com/user-attachments/files/28044622/TL.DTL.1.xls)

[Sơ đồ tổ chức.xlsx](https://github.com/user-attachments/files/28046258/S.d.t.ch.c.xlsx)
Sửa lại hệ thống theo nghiệp vụ này:
Tổng 5 role:admin,manager(MGR),supervisor(SV),leader(TL:tổ trưởng),staff(SL:tổ phó)
1.Chức năng tạo tài khoản và vai trò từng role:
- Admin:tạo được mọi loại tài khoản(gồm trường:username(bắt buộc),code,fullname(bắt buộc),gender,outlook,role(bắt buộc),nếu chọn role:staff thì sẽ phải chọn leader của staff đấy là ai,nếu chọn role:leader thì sẽ phải chọn supervisor của leader đấy là ai,nếu chọn role:supervisor thì sẽ phải chọn manager của supervisor đấy là ai,nếu chọn role:manager thì thôi không hiện gì nữa,bỏ trường Department,status(mặc định active),password,chọn mục thẩm quyền quản lý theo role
- Manager:tạo được tài khoản cho SV (username,code,fullname,gender,,outlook,pass,role mặc định supervisor,và khi MGR đấy tạo tài khoản SV thì SV đấy thuộc thẩm quyền quản lý của MGR luôn
- Supervisor:tạo được tài khoản cho leader (username,code,fullname,gender,pass,outlook,role mặc định leader,và khi SV đấy tạo tài khoản TL thì TL đấy thuộc thẩm quyền quản lý của SV luôn
- Leader:tạo được tài khoản cho staff (username,fullname,gender,pass,role mặc định staff,và khi TL đấy tạo tài khoản SL thì SL đấy thuộc thẩm quyền quản lý của TL luôn(code:sẽ tự động lấy code của leader xong thêm số:VD:hv90122 thì của staff sẽ là hv90122-SL1 và outlook của staff dùng sẽ là outlook của leader luôn)

2.Chức năng tự động gửi thông báo outlook
- Admin:Không cần thông báo
- Manager:Nhận thông báo của supervisor khi nộp checklist mỗi tháng
- Supervisor:Nhận thông báo khi manager xác nhận checklist tháng,nhận thông báo khi leader nộp checklist ngày(checklist tuần và tháng là chung 1 checklist trong tháng luôn,chỉ là tuần nào chưa điền thôi).Luôn có 1 nút chuông để nhắc nhở leader đấy nộp báo cáo.Nhận thông báo tự động vào tuần 4 thứ 6 cuối tháng 16h chiều là cần nộp báo cáo tháng cho manager,nếu nộp trước thời gian thông báo rồi thì thôi không thông báo nữa nhưng manager xác nhận checklist rồi thì leader vẫn sẽ nhận outlook là đã xác nhận checklist tháng đấy)
- Leader:Nhận thông báo khi SV xác nhận checklist ngày.Luôn có 1 nút chuông để nhắc nhở staff(chính là outlook của leader luôn) đấy nộp báo cáo.Nhận thông báo tự động vào cuối ca đấy trước 1 tiếng,ví dụ:ca 1 cuối ca là 13h thì 12h sẽ phải gửi thông báo nhắc nhở cần hoàn thành checklist ngày,nếu đã hoàn thành và nộp rồi thì thôi),leader xác nhận xong rồi thì cũng gửi về outlook 1 cái mail là xác nhận rồi
Ngắn gọn là:manager nhận tb cuối tháng,sv nhận tb cuối tuần,leader nhận tb mỗi ngày

3.Phân bố số lượng cho các role
- Manager(khoảng 5)
- Supervisor(khoảng 5 trên 1 manager)
- Leader(khoảng 3 trên 1 supervisor)
- Staff (khoảng 3 đến 4 trên 1 leader):Staff có 3 ca và staff có ca hành chính),có thể có 1 staff ca hàng chính và 3 staff chia vào 3 ca hoặc 1 staff ca hàng chính và 2 staff đảm nhiệm 3 ca(tức là luôn có 1 staff ca hành trình và 1 staff chỉ đc phụ trách tối đa 2 ca nên trong trường hợp 2 staff 3 ca thì cái này do leader đấy chia ca theo tuần,ca đc phép thay đổi trong 1 tuần sau khi leader chia xong tuần đấy thì cả tuần được xếp như thế,ca hành chính có thể leader đưa ai phụ trách ca hành chính còn đối với ca làm việc theo ca thì do staff đấy vào chọn ca để nhập,3 ca giờ lần lượt từ 06:00(hôm trước -> 05:00 hôm sau vd:chọn ngày 20 thì là 06:00 ngày 20 đến 05:00 ngày 21)

4.Cách chia ca làm việc (checklist của TL sẽ dùng chung với SL,checklist của SV sẽ dùng của checklist SV,thời gian cũng khác đấy )
- Sẽ được chia thành 2 checklist
- Checklist 1:Ca hành chính:8:20 -> 9:20 -> 10:00 -> 11:00 -> 13:00 -> 15:00 --> 16:00
- Checklist 2:Ca làm việc cho staff:
+ Ca 1: 6:00 -> 7:00 -> 8:00 -> 9:00 -> 11:00 -> 12:00 -> 13:00
+ Ca 2: 14:00 -> 15:00 -> 16:00 -> 17:00 -> 19:00 -> 20:00 -> 21:00
+ Ca 3: 22:00 -> 23:00 -> 00:00 -> 1:00 -> 3:00 -> 4:00 -> 5:00

5.Sửa và thêm database
- Thêm các database vào như trong excel ,tạm thời để Fullname,role,role thẩm quyền,username,password,cho tài khoản đấy khi đăng nhập tài khoản đấy tự làm thao tác update tài khoản thì điền nốt các thông tin đấy.Trong file excel có thông tin fullname,username,password(tạm thời để là 1),chia role và role ai thuộc thẩm quyền người đấy rồi đấy
- Sửa lại hết database đi,reset lại cũng được
- Có 2 checksheet đấy của tl và sv khác nhau đấy

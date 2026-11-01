# Các điểm cần đồng bộ giữa phần 5 và mã benchmark

## Biến thể được cài đặt

Phần 7 đo **tìm kiếm tiến có chặn kết hợp đảo hậu duyệt DFS**, ký hiệu `incremental_rpo` trong mã nguồn. Đây là cách được mô tả trong mã giả của bản thảo phần 5, bổ sung kiểm tra đầu vào và dùng DFS lặp. Nó không phải bản cài đặt thuật toán Pearce–Kelly hay Bender–Fineman–Gilbert–Tarjan.

Trạng thái gồm danh sách kề, `order` lưu đỉnh theo vị trí, `pos` lưu vị trí theo đỉnh và mảng đánh dấu theo thế hệ. Với cạnh u → v đã đúng thứ tự, chỉ cần chèn cạnh. Với cạnh ngược, tìm từ v nhưng chỉ đi đến các đỉnh có vị trí không vượt quá `pos[u]`. Nếu gặp u, từ chối ngay và giữ nguyên đồ thị cùng thứ tự.

Nếu không có chu trình, gọi W là cửa sổ từ `pos[v]` đến `pos[u]`, F là tập đỉnh đã tìm được, R = W \ F. Mã lấy R theo thứ tự hiện tại và F theo đảo hậu duyệt DFS, rồi ghi R trước F vào cửa sổ. Cạnh mới được chèn sau khi sửa thứ tự thành công.

## Vì sao sửa cửa sổ vẫn đúng

R giữ thứ tự tương đối cũ nên các cạnh nội bộ R vẫn hợp lệ. Đảo hậu duyệt của DFS trên đồ thị con được tìm kiếm cho một thứ tự hợp lệ trong F. Không có cạnh x → y với x thuộc F và y thuộc R: nếu có, y cũng đi tới được từ v và ở trong cửa sổ, nên phải thuộc F, mâu thuẫn.

Vì vậy, xếp R trước F không phá cạnh cũ giữa hai tập. Các đỉnh ngoài W giữ nguyên vị trí; do thứ tự trước cập nhật đã hợp lệ, các cạnh băng qua biên cửa sổ vẫn đi từ phần trước vào W hoặc từ W ra phần sau. Cuối cùng, u thuộc R và v thuộc F, nên cạnh mới u → v cũng được thỏa mãn.

Không mô tả bản cài đặt này là phân hoạch ổn định trong cả R và F: thứ tự trong F lấy theo đảo hậu duyệt, có thể khác thứ tự cũ. Muốn đổi sang phân hoạch ổn định, cần sửa đồng thời mã, mô tả và chạy lại số liệu.

## Chi phí theo đúng mã

Đặt V_s là số đỉnh được tìm kiếm, E_s là số phần tử danh sách kề thực sự được kiểm tra, gồm cả cạnh có đích ngoài cửa sổ bị loại bởi điều kiện chặn.

- Cạnh xuôi: O(1) khấu hao cho chèn cuối vector theo hợp đồng không trùng cạnh của workload. API mặc định có tìm cạnh trùng bằng quét danh sách kề, khi đó cộng O(outdegree(u)).
- Cạnh ngược hợp lệ: O(|V_s| + |E_s| + |W|), gồm cả thu thập R và ghi lại cửa sổ.
- Cạnh tạo chu trình: O(|V_s| + |E_s|), khi phát hiện trước khi sửa thứ tự.
- Trường hợp xấu nhất của một yêu cầu: O(n + m). Bộ nhớ phụ O(n), ngoài danh sách kề.

Mảng dấu thăm dùng thế hệ để không xóa O(n) phần tử sau mỗi yêu cầu. Khi bộ đếm thế hệ 32 bit quay vòng, mã xóa mảng một lần; trường hợp này có unit test riêng. Mọi nhánh phải tính cả cấp phát phát sinh nếu có; thời gian đo không loại chi phí đó.

## Trạng thái khi từ chối

Khuyên u → u bị từ chối ngay. Cạnh trùng không được thêm lần nữa. Khi một cạnh gây chu trình, tập cạnh, thứ tự và mảng vị trí được bảo toàn; dung lượng đã cấp phát hoặc dấu thăm nội bộ có thể được giữ lại để tái sử dụng, không được hiểu là bắt buộc mọi byte trạng thái đều giống trước yêu cầu.

Kiểm tra quan trọng sau mỗi cập nhật là: `order` là hoán vị, `order[pos[v]] == v` và mọi cạnh x → y thỏa `pos[x] < pos[y]`. Những điều kiện này đều được kiểm tra trong bộ kiểm chứng ngoài thời gian đo.

## Cách liên hệ với kết quả nghiên cứu

Baseline `kahn_guarded` chỉ tính lại khi thứ tự đang giữ bị vi phạm, tương tự nguyên tắc STO trong [Pearce và Kelly, Hình 1](https://whileydave.com/publications/PK07_JEA_preprint.pdf). Baseline `kahn_recompute` luôn chạy lại Kahn sau mỗi yêu cầu mới là đối tượng bắt buộc của đề cương; không đồng nhất hai baseline này.

Không sử dụng khẳng định “nhanh nhất thế giới”, không gán cận của một công trình nghiên cứu cho biến thể nhóm tự cài đặt, và không coi việc Kahn thay đổi thứ tự là ngẫu nhiên hoặc tự động gây mất cache. Đối với BFGT, cận trên toàn chuỗi là O(m·min{√m,n^(2/3)}) hoặc O(n² log n) cho hai thuật toán tương ứng, theo [bản tác giả](https://arxiv.org/abs/1112.0784); không viết thành O(m√n).

Nhận xét thực nghiệm trong phần 5 nên dẫn sang phần 7 và sử dụng chính số liệu mới đã đo. Các số “2,1–7 lần” trong bản thảo cũ không được thay thế cho kết quả mới nếu chưa xác định đầy đủ thí nghiệm gốc.

"""Assemble the Vietnamese report and slide notes directly from audited summary CSVs."""
from pathlib import Path
import csv
import json
from datetime import datetime
from build import ROOT
from summarize import read_csv
from plot_results import numeric,one,CASES,LABELS

def fmt(x,dec=0):
    return f'{x:,.{dec}f}'.replace(',','@').replace('.',',').replace('@','.')

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                     ['| '+' | '.join(str(x).replace('|',r'\|') for x in row)+' |' for row in rows])

def main():
    base=ROOT/'benchmark/results/full'
    rows=numeric(read_csv(base/'summary/summary.csv'))
    speeds=numeric(read_csv(base/'summary/speedups.csv'))
    env=json.loads((base/'environment.json').read_text(encoding='utf-8'))
    validation=json.loads((base/'summary/validation_summary.json').read_text())
    audit=json.loads((base/'summary/audit.json').read_text());assert audit['passed']
    unit=json.loads((ROOT/'benchmark/tests/validation_unit.json').read_text())
    nx=json.loads((ROOT/'benchmark/tests/validation_networkx.json').read_text())
    def a(f,n,m,alg):return one(rows,benchmark='static',family=f,n=n,m0=m,algorithm=alg)
    def b(f,alg,n=10000,m=None):return one(rows,benchmark='dynamic',family=f,n=n,m0=(0 if f=='window_only' else 5*n) if m is None else m,algorithm=alg)
    def sp(f,baseline='kahn_recompute',n=10000,m=None):return one(speeds,family=f,n=n,m0=(0 if f=='window_only' else 5*n) if m is None else m,baseline=baseline)['median_speedup']
    algs=['kahn_recompute','kahn_guarded','incremental_rpo']
    scale_table=table(['n','m','Kahn FIFO (ms)','DFS lặp (ms)'],[
        [fmt(n),fmt(5*n),fmt(a('sparse5',n,5*n,'kahn_fifo')['median_ns']/1e6,4),fmt(a('sparse5',n,5*n,'dfs_iterative')['median_ns']/1e6,4)] for n in [1000,5000,10000,50000]])
    density_table=table(['Mật độ','m với n = 1.000','Kahn FIFO (ms)','DFS lặp (ms)'],[
        [fmt(100*2*m/(1000*999),0)+'%',fmt(m),fmt(a('dense',1000,m,'kahn_fifo')['median_ns']/1e6,4),fmt(a('dense',1000,m,'dfs_iterative')['median_ns']/1e6,4)] for m in [24975,99900,249750]])
    dynamic_table=table(['Trường hợp','Kahn tính lại (µs)','Kahn kiểm tra trước (µs)','Cục bộ (µs)','S so với Kahn tính lại'],[
        [label]+[fmt(b(f,alg)['median_ns']/1000,3) for alg in algs]+[fmt(sp(f),2)] for f,label in zip(CASES,LABELS)])
    memory_static=table(['Họ đồ thị, n = 50.000','Payload phụ Kahn (KiB)','Payload phụ DFS (KiB)'],[
        [label,fmt(a(f,50000,m,'kahn_fifo')['aux_payload_bytes']/1024,1),fmt(a(f,50000,m,'dfs_iterative')['aux_payload_bytes']/1024,1)]
        for f,label,m in [('chain','Chuỗi dài',49999),('sparse5','DAG ngẫu nhiên m = 5n',250000),('layered','Phân tầng',250000)]])
    memory_dynamic=table(['Trường hợp, n = 10.000','Kahn tính lại (KiB)','Kahn kiểm tra trước (KiB)','Cục bộ (KiB)'],[
        [label]+[fmt(b(f,alg)['aux_payload_bytes']/1024,1) for alg in algs]
        for f,label in [('forward','Cạnh xuôi'),('local_small','Vùng nhỏ'),('local_large','Vùng lớn'),('cycle','Chu trình')]])
    work_table=table(['Trường hợp','Đỉnh tìm kiếm','Cạnh được xét','Độ dài W','Vị trí order được ghi'],[
        [label]+[fmt(b(f,'incremental_rpo')[k],2) for k in ['vertices','edge_checks','window_len','order_writes']]
        for f,label in zip(CASES[:5],LABELS[:5])])
    density_dynamic=table(['m₀, n = 1.000','Mật độ','S vùng lớn','S chu trình'],[
        [fmt(m),fmt(100*2*m/(1000*999),2)+'%',fmt(sp('local_large',n=1000,m=m),2),fmt(sp('cycle',n=1000,m=m),2)]
        for m in [2000,5000,49950,149850]])
    source=env['git_source_commit']
    date=datetime.fromisoformat(env['timestamp']).strftime('%d/%m/%Y')
    text=f'''# Phần 7 Benchmark và đánh giá thực nghiệm

## 7.1 Mục tiêu thực nghiệm

Phần thực nghiệm đánh giá chi phí tìm và duy trì thứ tự tô-pô trên các đồ thị phụ thuộc có quy mô, mật độ và dạng cập nhật khác nhau. Hai nhóm thí nghiệm được thực hiện: Benchmark A so sánh Kahn FIFO với DFS lặp trên đồ thị cố định; Benchmark B so sánh tính lại Kahn sau mỗi yêu cầu thêm cạnh với cập nhật thứ tự cục bộ. Một baseline Kahn có kiểm tra thứ tự trước khi tính lại được bổ sung để tách lợi ích của phép kiểm tra vị trí khỏi lợi ích của tìm kiếm và sửa thứ tự cục bộ.

Các giả thuyết cần kiểm tra là: thời gian của topo tĩnh tăng khi kích thước đồ thị tăng; cập nhật cục bộ có lợi khi tránh được phần lớn công việc toàn cục; và lợi thế có thể giảm hoặc đảo chiều khi phải tìm kiếm hoặc sửa một vùng lớn. Các phép đo đồng thời kiểm tra tính đúng đắn, vì thời gian thấp chỉ có ý nghĩa khi thứ tự và quyết định nhận hoặc từ chối cạnh đều hợp lệ.

Kết quả cho thấy cần xét cả vùng tác động, cách biểu diễn trạng thái và thứ tự mà từng phương pháp duy trì. Cập nhật cục bộ không nhanh hơn trong mọi trường hợp, ngay cả khi số cạnh được kiểm tra ít hơn baseline.

## 7.2 Thiết kế thí nghiệm

### 7.2.1 Môi trường và thuật toán

Thí nghiệm chạy ngày {date} trên một máy duy nhất, đơn luồng, với cấu hình sau.

{table(['Thành phần','Cấu hình'],[
    ['CPU',env['cpu']],['RAM vật lý',fmt(env['ram_bytes']/2**30,2)+' GiB' if env['ram_bytes'] else 'Không thu thập trên hệ điều hành này'],
    ['Hệ điều hành',env['platform']],
    ['Compiler',env['compiler'].splitlines()[0]+'; C++17'],
    ['Cờ biên dịch','-O3 -DNDEBUG -Wall -Wextra -Wpedantic'],
    ['Python và thư viện','Python '+env['python'].split()[0]+'; '+ '; '.join(k+' '+v for k,v in env['packages'].items())],
    ['Nguồn C++ được đo',source[:12]],
    ['Lặp và khởi động','5 seed × 10 lượt đo; 3 lượt khởi động cho mỗi workload và thuật toán']])}

Mọi thuật toán dùng danh sách kề `vector<vector<int>>` và cùng kiểu mã đỉnh. Kahn tĩnh tự tính bậc vào trong lần chạy; DFS dùng ngăn xếp tường minh và ba trạng thái để tránh phụ thuộc vào độ sâu đệ quy. Kahn dùng một vector làm hàng đợi FIFO với chỉ số đầu. Những lựa chọn cài đặt này được giữ cố định trong toàn bộ thí nghiệm.

Trong Benchmark B, `kahn_recompute` thêm cạnh ứng viên rồi chạy Kahn; nếu có chu trình, cạnh vừa thêm bị loại bỏ và thứ tự trước yêu cầu được giữ lại. `kahn_guarded` thực hiện cùng thao tác khi cạnh mới làm sai thứ tự đang giữ, còn với cạnh đã đúng thứ tự thì chỉ chèn cạnh. Nguyên tắc tính lại có điều kiện tương tự baseline STO được trình bày trong [1].

`incremental_rpo` là biến thể tìm kiếm tiến có chặn của phần 5: tìm từ v trong cửa sổ W khi thêm u → v làm sai thứ tự; nếu không tạo chu trình, xếp R trước F, với R giữ thứ tự cũ và F lấy theo đảo hậu duyệt DFS. Mã dùng mảng đánh dấu theo thế hệ để không xóa toàn bộ dấu thăm sau mỗi yêu cầu. Đây là bản cài đặt của biến thể đơn giản do nhóm lựa chọn, không phải thuật toán PK hay BFGT.

### 7.2.2 Dữ liệu và quy mô

Đợt đo gồm {validation['static_workloads']} workload tĩnh và {validation['dynamic_workloads']} workload động. Mỗi cấu hình có năm seed: 11, 23, 37, 53 và 71. Như vậy, Benchmark A có 29 cấu hình và Benchmark B có 27 cấu hình trước khi nhân số seed.

{table(['Nhóm dữ liệu','Cấu hình','Mục đích'],[
    ['Topo tĩnh thưa và có cấu trúc','n = 1.000, 5.000, 10.000, 50.000; chuỗi dài, ngẫu nhiên m = 2n hoặc 5n, phân tầng và không liên thông','Khảo sát quy mô, độ sâu và cách phân nhánh'],
    ['Topo tĩnh dày','n = 500, 1.000, 2.000; mật độ 5%, 20%, 50%','Tách ảnh hưởng số cạnh khỏi số đỉnh'],
    ['Cập nhật theo quy mô','n = 1.000, 5.000, 10.000; m₀ = 5n, riêng W lớn F nhỏ có m₀ = 0; q = 200','So sánh sáu loại workload cập nhật'],
    ['Cập nhật theo mật độ','n = 1.000; m₀ = 2.000, 5.000, 49.950, 149.850; q = 200','Khảo sát cạnh xuôi, vùng lớn và chu trình ở các mật độ khác nhau']])}

Với n ≥ 2, mật độ được tính bằng ρ = m/[n(n−1)/2]. Để sinh DAG ngẫu nhiên, bộ sinh tạo một hoán vị ẩn rồi chỉ chọn cạnh đi từ vị trí trước đến vị trí sau. Cạnh được lấy không hoàn lại để đạt đúng m yêu cầu. Họ phân tầng, không liên thông và các tình huống động có bộ sinh cấu trúc riêng. Đây là dữ liệu tổng hợp có kiểm soát, không phải lấy mẫu đồng đều trên toàn bộ tập DAG và chưa phải đồ thị CI/CD lấy từ một dự án đang vận hành.

Mỗi workload động chứa cùng G₀, cùng thứ tự ban đầu π₀ và cùng danh sách 200 yêu cầu cho cả ba phương pháp. Sau cập nhật, các phương pháp được phép giữ thứ tự khác nhau; yêu cầu đối chiếu là cùng tập cạnh được chấp nhận và cùng quyết định cho từng yêu cầu. Nhãn “vùng nhỏ” hoặc “vùng lớn” được xác định theo trạng thái của thuật toán cục bộ, không mặc định áp dụng cho thứ tự của baseline.

### 7.2.3 Các trường hợp và lý do lựa chọn

{table(['Trường hợp','Cách xây dựng','Nội dung kiểm chứng'],[
    ['Cạnh xuôi','Cạnh mới tuân theo thứ tự ban đầu','Lợi ích của việc không tính lại thứ tự'],
    ['Vùng nhỏ','Cạnh ngược trong một khối nhỏ; không tạo chu trình; W và số đỉnh tìm kiếm không quá 1% n','Lợi ích khi chi phí tìm kiếm và ghi mảng đều nhỏ'],
    ['Vùng lớn','Một chuỗi có khoảng 60% n đỉnh; lần lượt thêm các đỉnh nguồn phía sau làm tiền nhiệm của đầu chuỗi','Chi phí tìm kiếm nhiều đỉnh và sửa một cửa sổ lớn'],
    ['Chu trình','Đồ thị có chuỗi đi qua toàn bộ đỉnh; chèn cạnh ngược khép một đường đi dài','Quyết định từ chối và thời gian phát hiện'],
    ['W lớn nhưng F nhỏ','Đồ thị ban đầu rỗng; các cập nhật dịch một đỉnh đầu cửa sổ ra sau đỉnh gần cuối','Tách số đỉnh tìm kiếm khỏi chi phí quét và ghi cửa sổ'],
    ['Hỗn hợp','Chọn các cặp đỉnh mới trên DAG ngẫu nhiên, chấp nhận hoặc từ chối theo trạng thái hiện tại','Quan sát một chuỗi không chỉ gồm một loại quyết định'],
    ['Thay đổi n và mật độ','Lặp các nhóm phù hợp trên cấu hình ở mục 7.2.2','Đánh giá điều kiện mà lợi thế tăng, giảm hoặc đảo chiều']])}

Workload chính không có cạnh trùng và khuyên tự thân; điều kiện này được kiểm chứng trước khi đo. API mặc định vẫn kiểm tra hai trường hợp đó, nhưng lượt thời gian sử dụng hợp đồng cạnh mới để tránh đưa phép tìm cạnh trùng tuyến tính vào nhánh cạnh xuôi. Chi phí bổ sung của hợp đồng API được nêu ở bảng độ phức tạp bên dưới.

## 7.3 Kiểm chứng tính đúng đắn

Với một thứ tự trả về, bộ kiểm tra xác nhận có đúng n đỉnh, không trùng đỉnh và mọi cạnh u → v thỏa pos[u] < pos[v]. Đối với cập nhật, kiểm tra thêm tính nghịch đảo của `order` và `pos`. Một oracle tìm đường đi độc lập xác định cạnh mới có tạo chu trình hay không; nếu bị từ chối, tập cạnh, thứ tự và mảng vị trí phải được bảo toàn. NetworkX được dùng làm bộ đối chiếu ngoài mã C++ [2].

{table(['Bộ kiểm chứng','Phạm vi','Kết quả'],[
    ['Topo tĩnh trong C++','4.096 đồ thị có hướng không khuyên trên 4 đỉnh; đồ thị rỗng, một đỉnh và chuỗi 100.000 đỉnh',fmt(unit['static_result_checks'])+' kết quả đạt'],
    ['Chuyển trạng thái trong C++','543 DAG trên 4 đỉnh; 100 seed ngẫu nhiên; A–G, từ chối, cạnh trùng, tự nối; đối chiếu bản có và không có bộ đếm',fmt(unit['dynamic_transition_checks'])+' chuyển trạng thái đạt'],
    ['Đỉnh ngoài miền','Đầu mút âm hoặc lớn hơn chỉ số cuối',fmt(unit['invalid_vertex_checks'])+' kiểm tra đạt'],
    ['NetworkX '+nx['networkx_version'],str(nx['cases'])+' chuỗi, gồm chấp nhận, chu trình và cạnh trùng',fmt(nx['transition_order_checks'])+' đối chiếu quyết định và thứ tự đạt'],
    ['Đầu vào đo chính thức',str(validation['workloads'])+' workload; '+fmt(validation['distinct_update_attempts'])+' yêu cầu cập nhật khác nhau theo workload',fmt(validation['workload_result_checks'])+' kiểm tra kết quả và trạng thái đạt']])}

Các ngưỡng phân loại vùng nhỏ, vùng lớn, nhánh không tìm kiếm của cạnh xuôi, việc không ghi thứ tự khi từ chối và trường hợp F chỉ có một đỉnh đều được kiểm tra lại từ bộ đếm. Các lượt đo còn kiểm tra trạng thái cuối bên ngoài đồng hồ. Không có workload thất bại được đưa vào thống kê. Kết quả kiểm thử cung cấp bằng chứng cho các trường hợp đã xét; tính đúng đắn tổng quát vẫn dựa trên lập luận thuật toán ở phần 2 và phần 5.

## 7.4 Phương pháp đo và thống kê

Đồng hồ sử dụng là `std::chrono::steady_clock`. Topo tĩnh được đo từ danh sách kề có sẵn, tính cả khởi tạo cấu trúc phụ, tính bậc vào và tạo kết quả. Mỗi lượt có thể gồm nhiều lần chạy để giảm ảnh hưởng độ phân giải đồng hồ; số lần batch được chọn từ pilot, nhắm khoảng 3 ms và giới hạn 1.000. Thời gian batch được chia cho số lần chạy. Trong batch có cập nhật checksum O(1) cho mỗi kết quả; việc kiểm tra đầy đủ thứ tự diễn ra sau khi dừng đồng hồ.

Topo động được đo trên cả chuỗi 200 yêu cầu. Chi phí chèn cạnh, tìm kiếm, cấp phát phát sinh, sửa thứ tự và hoàn tác đều nằm trong phạm vi đo. Khởi tạo G₀ và trạng thái được đo riêng thành `setup_ns`, không cộng vào thời gian cập nhật chính. Các phương pháp đều bắt đầu từ bản sao mới ở từng lượt, kể cả sau lượt khởi động. Không tính sinh dữ liệu, đọc file, kiểm chứng, ghi CSV và vẽ giao diện. Thứ tự chạy các phương pháp được xáo trộn có seed qua các lượt; nguyên tắc khởi động và lặp đo tham khảo [3].

Với mỗi seed, lấy trung vị của 10 lượt đo; sau đó lấy trung vị giữa năm seed. Khoảng tứ phân vị IQR giữa seed được lưu trong CSV và biểu diễn bằng vùng tô hoặc thanh sai số. Đại lượng µs/yêu cầu là thời gian toàn chuỗi chia 200, không phải phân vị độ trễ của từng yêu cầu. Năm seed phản ánh các đầu vào trong thiết kế này; IQR không được diễn giải thành khoảng tin cậy thống kê.

Hệ số tăng tốc S được tính trên từng cặp cùng workload và seed: S = T(Kahn tính lại)/T(cục bộ), rồi lấy trung vị của năm tỷ số. S > 1 có lợi cho cục bộ; S < 1 có lợi cho baseline. Do cách tổng hợp theo cặp, S không nhất thiết bằng tỷ số của hai trung vị thời gian đã tổng hợp trong cùng bảng.

Một lượt instrument riêng ghi số đỉnh tìm kiếm hoặc xử lý, số phần tử danh sách kề được xét, độ dài cửa sổ và số thao tác ghi `order`, `pos`. Cạnh bị chặn ngoài cửa sổ vẫn được tính là một lần xét nếu mã đã đọc phần tử danh sách kề đó. Số vị trí được ghi khác với số đỉnh thật sự đổi vị trí. Với DFS, bộ đếm ghi thứ tự còn tính thao tác đảo kết quả.

Bộ nhớ được tính từ capacity thực của các vector trong lượt instrument và lấy đỉnh dung lượng quan sát trên chuỗi. Payload đồ thị gồm vùng lưu vector danh sách kề và các phần tử cạnh; payload phụ gồm các mảng, hàng đợi, ngăn xếp, thứ tự kết quả và bộ đệm cập nhật. Các giá trị sau không phải RAM đỉnh của tiến trình: chúng chưa tính metadata của allocator, đối tượng cục bộ trên stack, runtime và bản sao phục vụ harness. Lượt thời gian được biên dịch không có các bộ đếm để giảm tác động đo lên thuật toán.

## 7.5 Kết quả và thảo luận

### 7.5.1 Thuật toán topo tĩnh

**Bảng 7.1 Thời gian trên DAG ngẫu nhiên thưa với m = 5n**

{scale_table}

![Thời gian topo tĩnh](../benchmark/results/full/figures/Hinh_7_1_Topo_tinh.png)

**Hình 7.1.** Thời gian Kahn FIFO và DFS lặp khi tăng quy mô và mật độ. Ô (a) dùng trục log cho cả n và thời gian; ô (b) giữ n = 1.000. Vùng tô biểu diễn IQR giữa seed.

Trong dải m = 5n, thời gian của cả hai tăng khi n tăng. Kahn tăng từ {fmt(a('sparse5',1000,5000,'kahn_fifo')['median_ns']/1e6,4)} ms ở n = 1.000 lên {fmt(a('sparse5',50000,250000,'kahn_fifo')['median_ns']/1e6,4)} ms ở n = 50.000; DFS tăng từ {fmt(a('sparse5',1000,5000,'dfs_iterative')['median_ns']/1e6,4)} ms lên {fmt(a('sparse5',50000,250000,'dfs_iterative')['median_ns']/1e6,4)} ms. Kahn có trung vị thấp hơn DFS trên các cấu hình được nêu trong bảng, nhưng kết quả này chỉ gắn với các bản cài đặt và dữ liệu đã đo.

**Bảng 7.2 Thời gian khi giữ n = 1.000 và tăng mật độ**

{density_table}

Số cạnh tăng làm thời gian tăng ở cả hai phương pháp. Bộ đếm của Kahn trên DAG hợp lệ gồm m lần xét để tính bậc vào và m lần khi xử lý cạnh; DFS xét mỗi phần tử danh sách kề một lần, nhưng còn thực hiện các thao tác trạng thái và ngăn xếp. Vì vậy, ít lần xét cạnh hơn chưa đủ để dự đoán phương pháp nhanh hơn. Kết quả hỗ trợ xu hướng tăng chi phí theo kích thước đầu vào, không chứng minh quan hệ thời gian tỷ lệ chính xác với n + m trên toàn dải; hệ số thực tế còn có thể chịu ảnh hưởng của cấp phát, truy cập bộ nhớ và trạng thái máy mà thí nghiệm này chưa tách riêng.

### 7.5.2 Cập nhật thứ tự theo từng tình huống

**Bảng 7.3 Thời gian trung bình mỗi yêu cầu, tổng hợp theo seed**

Các dòng dùng n = 10.000, q = 200, m₀ = 50.000; riêng W lớn F nhỏ có m₀ = 0. Workload chu trình có 200 yêu cầu bị từ chối; không gọi đó là 200 cạnh đã được thêm thành công.

{dynamic_table}

![Thời gian cập nhật](../benchmark/results/full/figures/Hinh_7_2_Thoi_gian_cap_nhat.png)

**Hình 7.2.** Thời gian cập nhật trên sáu workload. Trục đứng là log, đơn vị µs/yêu cầu; thanh sai số là IQR giữa seed.

**Cạnh xuôi.** Cục bộ chỉ mất {fmt(b('forward','incremental_rpo')['median_ns']/1000,3)} µs/yêu cầu, so với {fmt(b('forward','kahn_recompute')['median_ns']/1000,3)} µs của Kahn luôn tính lại. Tuy nhiên, Kahn kiểm tra trước cũng chỉ mất {fmt(b('forward','kahn_guarded')['median_ns']/1000,3)} µs và không chạy lại lần nào. Do đó, lợi ích chính ở đây đến từ việc phát hiện thứ tự cũ vẫn dùng được; chưa cần tìm kiếm cục bộ. Hệ số tăng tốc rất lớn trước baseline luôn tính lại không nên được dùng làm một con số đại diện cho mọi dạng cập nhật.

**Vùng nhỏ.** Cục bộ đạt S = {fmt(sp('local_small'),2)} so với Kahn tính lại và S = {fmt(sp('local_small','kahn_guarded'),2)} so với Kahn kiểm tra trước. Mỗi yêu cầu chỉ tìm {fmt(b('local_small','incremental_rpo')['vertices'])} đỉnh và ghi {fmt(b('local_small','incremental_rpo')['order_writes'])} vị trí `order`. Đây là trường hợp hỗ trợ rõ giả thuyết lợi ích khi công việc cục bộ nhỏ so với toàn đồ thị.

**Vùng lớn.** Cục bộ mất {fmt(b('local_large','incremental_rpo')['median_ns']/1000,3)} µs, cao hơn {fmt(b('local_large','kahn_recompute')['median_ns']/1000,3)} µs của Kahn tính lại; S = {fmt(sp('local_large'),2)}. Thuật toán cục bộ tìm 6.000 đỉnh, xét 50.000 cạnh và ghi 6.001 vị trí cho mỗi yêu cầu. Việc tránh một phần duyệt toàn cục không bù được toàn bộ chi phí DFS và sắp lại trong cấu hình này.

Baseline Kahn kiểm tra trước chỉ mất {fmt(b('local_large','kahn_guarded')['median_ns']/1000,3)} µs/yêu cầu. Bộ đếm cho thấy nó chỉ tính lại một lần trên cả 200 yêu cầu. Sau lần đó, thứ tự mới đưa các đỉnh nguồn còn lại lên trước chuỗi phụ thuộc, khiến các yêu cầu tiếp theo trở thành cạnh xuôi đối với baseline. Trong khi đó, chúng tiếp tục vi phạm thứ tự mà biến thể cục bộ đang giữ. Đây là hệ quả quan trọng của việc một DAG có nhiều thứ tự hợp lệ: cùng chuỗi cạnh không đồng nghĩa với cùng vùng tác động cho mọi thuật toán. Workload này có cấu trúc được chọn trước, nên không suy tỷ lệ một lần tính lại đó cho một hệ thống CI/CD bất kỳ.

**Chu trình.** Cả ba phương pháp từ chối đúng toàn bộ yêu cầu. Dù cục bộ chỉ xét trung bình khoảng {fmt(b('cycle','incremental_rpo')['edge_checks'])} cạnh, thấp hơn khoảng {fmt(b('cycle','kahn_recompute')['edge_checks'])} của Kahn, nó vẫn chậm hơn: {fmt(b('cycle','incremental_rpo')['median_ns']/1000,3)} µs so với {fmt(b('cycle','kahn_recompute')['median_ns']/1000,3)} µs; S = {fmt(sp('cycle'),2)}. Chuỗi phụ thuộc dài buộc cục bộ tìm kiếm sâu, còn Kahn dừng khi không còn đỉnh sẵn sàng sau giai đoạn tính bậc vào. Kết quả cho thấy bộ đếm cạnh cần được đọc cùng cách tổ chức thao tác, thay vì coi mọi lần xét cạnh có chi phí bằng nhau.

**W lớn nhưng F nhỏ.** Mỗi yêu cầu chỉ tìm một đỉnh nhưng ghi trung bình 9.801 vị trí. Vì vậy thời gian cục bộ vẫn là {fmt(b('window_only','incremental_rpo')['median_ns']/1000,3)} µs, cao hơn {fmt(b('window_only','kahn_guarded')['median_ns']/1000,3)} µs của baseline kiểm tra trước. Trường hợp này trực tiếp cho thấy cần cộng chi phí |W| vào phân tích của bản cài đặt mảng.

**Chuỗi hỗn hợp.** Cục bộ có trung vị {fmt(b('mixed','incremental_rpo')['median_ns']/1000,3)} µs và S = {fmt(sp('mixed'),2)} trước Kahn tính lại. Số yêu cầu được nhận hoặc bị từ chối được lưu riêng; tại cấu hình này, trung vị giữa seed là {fmt(b('mixed','incremental_rpo')['accepted'])} yêu cầu nhận và {fmt(b('mixed','incremental_rpo')['cycles'])} yêu cầu chu trình. Đây vẫn là các cặp đỉnh tổng hợp, chưa đủ để xem là phân phối cập nhật của một ứng dụng thực.

### 7.5.3 Liên hệ thời gian với lượng công việc

**Bảng 7.4 Công việc của cập nhật cục bộ, trung bình mỗi yêu cầu tại n = 10.000**

{work_table}

![Lượng công việc](../benchmark/results/full/figures/Hinh_7_3_Luong_cong_viec.png)

**Hình 7.3.** So sánh công việc duyệt cạnh của ba phương pháp và số đỉnh tìm kiếm so với số vị trí được ghi của cập nhật cục bộ. Các giá trị được lấy trung bình trong từng workload rồi tổng hợp trung vị giữa seed. Độ dài W của yêu cầu chu trình chỉ biểu thị phạm vi cho phép tìm kiếm, không có nghĩa là thuật toán đã quét hoặc ghi toàn bộ cửa sổ đó.

Vùng nhỏ có cả số đỉnh tìm kiếm lẫn số vị trí ghi thấp. Vùng lớn có hai đại lượng đều lớn. Trường hợp W lớn F nhỏ tách được hai thành phần chi phí: tìm kiếm rất ít nhưng sửa mảng gần như toàn bộ thứ tự. Các quan sát này phù hợp với cận O(|V_s| + |E_s| + |W|) của nhánh cập nhật hợp lệ trong bản cài đặt đang đo.

### 7.5.4 Ảnh hưởng của quy mô và mật độ

![Ảnh hưởng quy mô và mật độ](../benchmark/results/full/figures/Hinh_7_4_Quy_mo_va_mat_do.png)

**Hình 7.4.** Hệ số tăng tốc theo cặp trước Kahn tính lại; đường đứt S = 1 phân chia hai phía có lợi. Ô (a) dùng trục đứng log; trường hợp W lớn F nhỏ có m₀ = 0. Vùng tô là IQR giữa seed.

Với m₀ = 5n, hệ số của vùng nhỏ tăng từ {fmt(sp('local_small',n=1000),2)} ở n = 1.000 lên {fmt(sp('local_small'),2)} ở n = 10.000, trong khi kích thước khối cục bộ vẫn nhỏ. Ngược lại, workload vùng lớn không đạt S > 1 tại ba quy mô chính. Đây là bằng chứng về sự phụ thuộc vào dạng tác động, không chỉ số đỉnh toàn đồ thị.

**Bảng 7.5 Ảnh hưởng mật độ đối với vùng lớn và chu trình**

{density_dynamic}

Ở n = 1.000, việc tăng mật độ chưa làm biến thể cục bộ thắng Kahn tính lại trong workload vùng lớn. Tuy nhiên, với yêu cầu tạo chu trình, S chuyển từ dưới 1 sang trên 1 khi số cạnh tăng. Trong bộ sinh chu trình, các cạnh của chuỗi được lưu trước các cạnh bổ sung nên DFS có thể gặp đường đi khép chu trình trước khi phải xét mọi cạnh bổ sung. Kahn vẫn tính bậc vào trên toàn bộ cạnh ứng viên. Thứ tự lưu cạnh là một điều kiện cụ thể của thí nghiệm này và cần được công bố khi diễn giải kết quả.

### 7.5.5 Bộ nhớ và độ phức tạp

**Bảng 7.6 Payload bộ nhớ phụ của các bản cài đặt topo tĩnh**

{memory_static}

**Bảng 7.7 Payload bộ nhớ phụ của các bản cài đặt cập nhật**

{memory_dynamic}

KiB = 1.024 byte. Mỗi giá trị trong hai bảng là trung vị giữa seed của dung lượng đỉnh quan sát trong lượt instrument. Kahn tĩnh đặt trước capacity n cho queue và kết quả, nên payload phụ tăng theo ba vector số nguyên kích thước n. DFS có mảng màu nhỏ hơn nhưng ngăn xếp phụ thuộc độ sâu: trên chuỗi dài, capacity ngăn xếp tăng làm payload cao hơn Kahn; trên DAG ngẫu nhiên và phân tầng, payload thấp hơn. Cục bộ cần thêm mảng vị trí, dấu thăm và bộ đệm; trong vùng lớn và chu trình, dung lượng phụ có thể cao hơn baseline.

{table(['Phương pháp hoặc nhánh','Thời gian','Bộ nhớ phụ'],[
    ['Kahn FIFO hoặc DFS lặp, một lần','O(n + m)','O(n)'],
    ['Kahn luôn tính lại, một yêu cầu','O(n + m)','O(n)'],
    ['Kahn kiểm tra trước, cạnh xuôi','O(1) khấu hao','O(n) trạng thái duy trì'],
    ['Cục bộ, cạnh xuôi','O(1) khấu hao','O(n) trạng thái duy trì'],
    ['Cục bộ, cạnh ngược hợp lệ','O(|V_s| + |E_s| + |W|)','O(n)'],
    ['Cục bộ, phát hiện chu trình trước sửa','O(|V_s| + |E_s|)','O(n)'],
    ['Cục bộ, trường hợp xấu nhất','O(n + m) mỗi yêu cầu','O(n)']])}

Các cận cạnh xuôi giả sử cạnh mới đã được bảo đảm không trùng và phép chèn cuối vector có chi phí khấu hao hằng số. Nếu dùng API mặc định quét danh sách kề để kiểm tra cạnh trùng, cộng O(outdegree(u)). Bộ nhớ đồ thị O(n + m) không nằm trong cột bộ nhớ phụ. Không gán cho biến thể này cận khấu hao của các thuật toán nghiên cứu chưa được cài đặt.

### 7.5.6 Kết luận và giới hạn

Thí nghiệm hỗ trợ lợi ích của tận dụng thứ tự cũ khi tác động nhỏ, đồng thời ghi nhận các trường hợp cục bộ chậm hơn baseline. Baseline có kiểm tra thứ tự cho thấy một phần cải thiện lớn trước cách luôn tính lại có thể đạt được chỉ bằng phép kiểm tra vị trí; trong một số chuỗi có cấu trúc, thứ tự sau tính lại còn làm giảm mạnh số lần cần xử lý tiếp theo.

Vì vậy, nên cân nhắc cập nhật cục bộ khi thường xuyên có các yêu cầu làm sai thứ tự nhưng vùng tìm kiếm và vùng ghi mảng nhỏ. Với đồ thị cố định, xử lý theo lô hoặc vùng tác động lớn, cần đối chiếu với thuật toán tĩnh và baseline có kiểm tra trước thay vì mặc định dùng phương pháp cải tiến.

Phạm vi kết luận giới hạn ở một máy, một compiler, một cách biểu diễn danh sách kề và các bộ sinh đã mô tả. Chưa đo đồ thị CI/CD thực, tác động đến cache build, cập nhật xóa cạnh, lập lịch có giới hạn tài nguyên hoặc hiệu năng của PK/BFGT. Không dùng các số liệu hữu hạn này để chứng minh cận tiệm cận hoặc suy ra một hệ số tăng tốc chung cho mọi hệ thống.

## Tài liệu tham khảo của phần 7

[1] D. J. Pearce và P. H. J. Kelly. *A Dynamic Topological Sort Algorithm for Directed Acyclic Graphs*. ACM Journal of Experimental Algorithmics, 11, Article 1.7, 2007. [Bản tác giả](https://whileydave.com/publications/PK07_JEA_preprint.pdf), Hình 1 và phần thực nghiệm. Chỉ tham khảo nguyên tắc baseline và phương pháp; số liệu trong phần này được đo mới.

[2] NetworkX Developers. [Directed Acyclic Graphs](https://networkx.org/documentation/stable/reference/algorithms/dag.html). Mã đối chiếu sử dụng phiên bản 3.4.2, được ghi trong biên bản kiểm chứng.

[3] Google Benchmark. [User Guide](https://github.com/google/benchmark/blob/main/docs/user_guide.md), các mục warmup, repetitions, statistics và memory usage. Harness của nhóm được cài riêng bằng C++17.

[4] MIT OpenCourseWare. [6.006 Lecture 14 — DFS và topological sorting](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/mit6_006f11_lec14/). Nguồn cơ sở thuật toán, xem phần 2 và phần 4 của seminar.

## Dữ liệu và khả năng tái lập

Mã nguồn được quản lý tại [Solitudeshu/topological-sorting](https://github.com/Solitudeshu/topological-sorting). Phiên bản C++ được đo có commit `{source}`; SHA-256 executable và mã nguồn nằm trong [environment.json](../benchmark/results/full/environment.json). Các lần cập nhật mã phân tích hoặc nội dung báo cáo sau đó không thay đổi executable đã dùng để đo.

Đợt chạy tạo {fmt(validation['timing_rows'])} dòng thời gian và {fmt(validation['instrumented_rows'])} dòng bộ đếm. Toàn bộ {audit['archived_inputs_verified']} đầu vào gzip đã được kiểm tra SHA-256 với manifest. [README](../README.md) ghi các lệnh build, kiểm thử, chạy lại và sinh biểu đồ. [Manifest](../benchmark/results/full/manifest.json), [CSV tổng hợp](../benchmark/results/full/summary/summary.csv), [tỷ số theo seed](../benchmark/results/full/summary/speedups_per_seed.csv), [biên bản kiểm chứng](../benchmark/results/full/summary/validation_summary.json) và [kiểm tra dữ liệu lưu trữ](../benchmark/results/full/summary/audit.json) được lưu cùng repository.
'''
    report=ROOT/'report';report.mkdir(exist_ok=True)
    (report/'Phan7_BaoCao.md').write_text(text,encoding='utf-8')
    slide=f'''# Nội dung phần 7 cho ba slide trong 4 phút

Chữ xanh là nội dung chọn đưa lên slide; đoạn lời dẫn nằm trong ghi chú người trình bày. Bảng và hình đầy đủ ở [báo cáo](Phan7_BaoCao.md). Toàn bộ số được sinh từ cùng CSV của đợt chạy chính thức.

## Slide 1 Thiết kế và kiểm chứng trước khi đo

**Thời lượng 45 giây.** Dùng sơ đồ hai nhánh tĩnh/động, không trình bày cấu trúc repository.

- <span style="color:#0000FF">Topo tĩnh: Kahn FIFO và DFS lặp.</span>
- <span style="color:#0000FF">Topo động: Kahn tính lại, Kahn kiểm tra trước và cập nhật cục bộ.</span>
- <span style="color:#0000FF">Cùng đầu vào; 5 seed × 10 lượt đo, 3 lượt khởi động; kiểm tra thứ tự và chu trình trước khi đo.</span>
- <span style="color:#0000FF">280 workload; thời gian đo không gồm giao diện, sinh dữ liệu và kiểm chứng.</span>

**Lời dẫn:** “Nhóm so sánh riêng topo tĩnh và cập nhật thứ tự. Ở bài toán động, nhóm thêm baseline Kahn kiểm tra vị trí trước khi tính lại để so sánh chặt chẽ hơn. Các phương pháp chạy cùng dữ liệu trên một máy; mỗi cấu hình có năm seed và mười lượt đo sau khởi động. Kết quả được kiểm tra trước khi đưa vào thống kê.”

## Slide 2 Chi phí topo tĩnh tăng theo quy mô và mật độ

**Thời lượng 45 giây.** Dùng Hình 7.1; giải thích trục trước khi đọc xu hướng.

![Kết quả topo tĩnh](../benchmark/results/full/figures/Hinh_7_1_Topo_tinh.png)

- <span style="color:#0000FF">Kahn và DFS đều tăng thời gian khi n hoặc m tăng.</span>
- <span style="color:#0000FF">m = 5n, n = 50.000: Kahn {fmt(a('sparse5',50000,250000,'kahn_fifo')['median_ns']/1e6,3)} ms; DFS {fmt(a('sparse5',50000,250000,'dfs_iterative')['median_ns']/1e6,3)} ms.</span>
- <span style="color:#0000FF">Cùng O(n + m); chênh lệch thực tế phụ thuộc bản cài đặt và dữ liệu.</span>

**Lời dẫn:** “Hình bên trái tăng số đỉnh với số cạnh bằng năm lần số đỉnh; hình bên phải giữ số đỉnh và tăng mật độ. Cả hai thuật toán đều tăng thời gian. Trong bản cài đặt này Kahn có trung vị thấp hơn trên các cấu hình minh họa, nhưng việc DFS xét ít cạnh hơn không tự bảo đảm nó nhanh hơn, vì còn có thao tác ngăn xếp và trạng thái. Đây là đối chiếu thực nghiệm, không phải chứng minh một thuật toán luôn thắng.”

## Slide 3 Cập nhật cục bộ có lợi khi vùng tác động nhỏ

**Thời lượng 2 phút 30 giây.** Dùng Hình 7.2 là hình chính. Có thể đặt ba số đếm ngắn dưới hình; không ép thêm toàn bộ Hình 7.3 vào cùng slide.

![Kết quả cập nhật](../benchmark/results/full/figures/Hinh_7_2_Thoi_gian_cap_nhat.png)

- <span style="color:#0000FF">Vùng nhỏ: tìm 7 đỉnh, ghi 8 vị trí; S = {fmt(sp('local_small'),2)} so với Kahn tính lại.</span>
- <span style="color:#0000FF">Vùng lớn: S = {fmt(sp('local_large'),2)}; chu trình: S = {fmt(sp('cycle'),2)}. Cục bộ có thể chậm hơn.</span>
- <span style="color:#0000FF">W lớn, F nhỏ: tìm 1 đỉnh nhưng ghi 9.801 vị trí.</span>
- <span style="color:#0000FF">Kahn kiểm tra trước cũng tránh tính lại ở cạnh xuôi; cần chọn theo workload.</span>

Ghi nhỏ dưới hình: “n = 10.000; q = 200; m₀ = 50.000, riêng W lớn F nhỏ có m₀ = 0. Trục thời gian log. S là trung vị tỷ số theo cặp seed; S > 1 có lợi cho cục bộ.” Nguồn số liệu: thí nghiệm nhóm, repository này.

**Chia lời dẫn:**

- **90 giây cho thời gian:** “Với cạnh xuôi, cả cục bộ và Kahn kiểm tra trước đều bỏ được phép tính lại. Khi vùng sửa nhỏ, cục bộ có lợi rõ vì mỗi yêu cầu chỉ chạm rất ít đỉnh. Nhưng ở vùng lớn và chu trình, hệ số dưới một cho thấy cục bộ chậm hơn Kahn tính lại. Đặc biệt, trong workload vùng lớn, Kahn kiểm tra trước chỉ tính lại một lần rồi thứ tự mới khiến các yêu cầu sau trở thành cạnh xuôi. Vì vậy, cùng chuỗi cập nhật không có nghĩa là mọi phương pháp giữ cùng thứ tự hoặc cùng vùng tác động.”
- **45 giây cho nguyên nhân:** “Bộ đếm giúp giải thích kết quả: vùng nhỏ chỉ tìm bảy đỉnh và ghi tám vị trí; vùng lớn phải tìm sáu nghìn đỉnh và ghi sáu nghìn lẻ một vị trí. Ngay cả khi chỉ tìm một đỉnh, cửa sổ lớn vẫn làm phải ghi gần toàn bộ mảng thứ tự. Do đó, phân tích cần tính cả độ dài cửa sổ, không chỉ số đỉnh được tìm.”
- **15 giây chốt:** “Kết quả ủng hộ cập nhật cục bộ khi tác động nhỏ, đồng thời cho thấy nó không luôn nhanh hơn. Kết luận hiện giới hạn ở dữ liệu tổng hợp và bản cài đặt đã đo; từ đó nhóm trở lại ba câu hỏi đầu bài để tổng kết.”

## Những nội dung giữ trong report hoặc slide dự phòng

Bảng bộ nhớ, chứng minh, các lệnh chạy, toàn bộ ma trận dữ liệu, biểu đồ mật độ Hình 7.4 và các CSV không cần đọc trong 4 phút. Nếu được hỏi về tính công bằng, giải thích cùng G₀, π₀ và chuỗi yêu cầu, nhưng cho phép thứ tự sau cập nhật khác nhau. Nếu được hỏi về hệ số rất lớn ở cạnh xuôi, nhấn mạnh baseline Kahn kiểm tra trước có nhánh nhanh tương tự.
'''
    (report/'Phan7_Slide.md').write_text(slide,encoding='utf-8')
    print('Wrote report/Phan7_BaoCao.md and report/Phan7_Slide.md')

if __name__=='__main__':main()

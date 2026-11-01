# Topological sorting seminar

Mã nguồn và kết quả thực nghiệm cho phần 7 của seminar: so sánh topo tĩnh và duy trì thứ tự khi thêm cạnh. Báo cáo dùng cùng ví dụ CI/CD A–G ở các phần trước. Các phép đo chạy bằng C++17, phân tích và biểu đồ được sinh bằng Python.

## Đọc kết quả

- [Báo cáo phần 7](report/Phan7_BaoCao.md).
- [Nội dung ba slide và lời dẫn trong 4 phút](report/Phan7_Slide.md).
- [Mô tả thuật toán và lưu ý để đồng bộ phần 5](report/DongBo_Phan5.md).
- [Môi trường chạy chính thức](benchmark/results/full/environment.json), [manifest đầu vào](benchmark/results/full/manifest.json), [số liệu tổng hợp](benchmark/results/full/summary/summary.csv), [hệ số tăng tốc](benchmark/results/full/summary/speedups.csv).
- Biểu đồ PNG và SVG ở `benchmark/results/full/figures/`; từng lần đo và từng cập nhật ở `benchmark/results/full/raw/`.

## Các thuật toán

`benchmark/include/topo.hpp` chứa Kahn FIFO, DFS lặp và ba phương pháp xử lý cập nhật: `kahn_recompute`, `kahn_guarded`, `incremental_rpo`. Phương pháp cục bộ là tìm kiếm tiến có chặn và sắp R trước F, với F theo đảo hậu duyệt DFS; không phải bản cài đặt PK hoặc BFGT. Mọi phương pháp nhận hoặc từ chối từng yêu cầu, giữ nguyên tập cạnh và thứ tự khi có chu trình. API mặc định kiểm tra đỉnh không hợp lệ, cạnh trùng và khuyên tự thân.

Workload đo hiệu năng được kiểm chứng không có cạnh trùng hoặc khuyên trước khi đo. Với hợp đồng này, mọi phương pháp gọi nhánh `novel=true` để bỏ chi phí tìm cạnh trùng bằng quét danh sách kề. Đây là điều kiện cần công bố khi diễn giải nhánh cạnh xuôi O(1) khấu hao. Xem `report/DongBo_Phan5.md`.

## Chạy trên Windows

Cần Python 3.11 và GCC hỗ trợ C++17 (đặt `g++` trên PATH). Từ thư mục gốc repository:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r benchmark/requirements.txt
.venv/Scripts/python.exe benchmark/scripts/build.py
benchmark/build/topo_tests.exe benchmark/tests/validation_unit.json
.venv/Scripts/python.exe benchmark/scripts/verify_networkx.py
.venv/Scripts/python.exe benchmark/scripts/run_benchmarks.py --profile quick --skip-build
.venv/Scripts/python.exe benchmark/scripts/summarize.py --profile quick
.venv/Scripts/python.exe benchmark/scripts/plot_results.py --profile quick
```

Để chạy lại toàn bộ phép đo, thay `quick` bằng `full` trong ba lệnh cuối. Chạy tuần tự để tác vụ khác không gây tải CPU cạnh tranh trong lượt đo chính thức. Các lệnh sẽ ghi lại kết quả của profile tương ứng; muốn giữ một lần đo cũ, sao chép thư mục kết quả sang tên khác trước khi chạy. Không dùng số liệu của hai máy để tạo một phép so sánh cặp.

Trên Linux/macOS, dùng `.venv/bin/python` và executable không có đuôi `.exe`. `build.py` tự nhận `g++` hoặc `clang++`. Có thể dùng CMake thay cho build script:

```text
cmake -S benchmark -B benchmark/build -DCMAKE_BUILD_TYPE=Release
cmake --build benchmark/build --config Release
ctest --test-dir benchmark/build -C Release --output-on-failure
```

Với CMake đa cấu hình trên Windows, executable nằm dưới `benchmark/build/Release`; các script Python mặc định sử dụng đường dẫn của `build.py`. Dùng build script cho chuỗi lệnh tái lập bên trên.

## Kiểm chứng và dữ liệu

- Unit test xét toàn bộ 4.096 đồ thị không khuyên trên bốn đỉnh, 543 DAG, chuỗi dài 100.000 đỉnh, ví dụ A–G, hoàn tác, đỉnh ngoài miền, cạnh trùng, khuyên tự thân và 100 seed ngẫu nhiên.
- Hai template có và không có bộ đếm được đối chiếu từng bước trong unit test. Khi đo, bộ đếm bị loại tại thời điểm biên dịch bằng `if constexpr`.
- NetworkX kiểm tra độc lập 31 chuỗi, gồm các lần chấp nhận, từ chối chu trình và cạnh trùng. Script xuất biên bản JSON.
- Mỗi workload chính thức được kiểm tra sau từng yêu cầu bằng oracle reachability độc lập và kiểm tra thứ tự trên toàn bộ cạnh trước khi chạy thời gian. Lượt có bộ đếm và lượt đo thời gian chạy riêng. Lượt đo còn kiểm tra trạng thái cuối bên ngoài đồng hồ.
- Đầu vào chính thức được lưu dưới dạng gzip xác định ở `benchmark/data/full/`. Manifest lưu SHA-256 của cả dữ liệu giải nén và file gzip. Không cần tải dữ liệu bên ngoài để xem hoặc chạy lại một đầu vào.
- Bộ sinh có phiên bản và seed trong `workloads.py`; cấu hình ở `benchmark/configs/`. Bộ sinh dựa trên hoán vị ẩn, không lấy mẫu đồng đều trên toàn bộ tập DAG.

Định dạng `.dag` sau giải nén: dòng đầu `TOPO_WORKLOAD_V1`; dòng tiếp theo `n m q`; dòng thứ ba là thứ tự ban đầu; sau đó m dòng cạnh ban đầu và q dòng yêu cầu thêm cạnh. Đỉnh được đánh số từ 0. Để chạy một input đã giải nén:

```text
topo_bench --input path/to/input.dag --out path/to/output --repeats 10 --warmups 3
```

`--mode validate` chỉ kiểm chứng; `--mode trace` cho phép cả cạnh trùng và khuyên, xuất quyết định và thứ tự sau mỗi yêu cầu vào `trace.jsonl` để đối chiếu bên ngoài.

## Phạm vi đo

Topo tĩnh: từ danh sách kề có sẵn, tính cả mảng làm việc, bậc vào, kết quả và giải phóng kết quả cũ giữa các lần trong batch. Batch thích nghi nhắm khoảng 3 ms theo pilot, tối đa 1.000 lần; CSV lưu batch thực tế. Chia thời gian batch cho số lần để tính chi phí một lần sắp xếp.

Topo động: đo cả chuỗi q yêu cầu, tính chèn cạnh, tìm kiếm, cấp phát phát sinh, sắp lại hoặc hoàn tác. Ghi riêng thời gian khởi tạo trạng thái; khởi tạo gồm sao chép G₀, π₀, tạo mảng và kiểm tra thứ tự ban đầu. Không tính sinh dữ liệu, đọc tệp, validation, ghi CSV và vẽ hình vào thời gian cập nhật. Không bấm giờ từng yêu cầu rất ngắn; số µs/yêu cầu là tổng thời gian chia q, không phải p95 độ trễ.

Bộ nhớ được tính từ capacity thực của các vector trong lượt instrument: đây là dung lượng payload cấp phát theo bản cài đặt, không phải RAM đỉnh của tiến trình. Tách payload đồ thị khỏi payload phụ, không tính allocator metadata, đối tượng vector đặt trên stack, runtime và các bản sao phục vụ harness. Các bộ đếm thao tác có định nghĩa trong báo cáo.

## Nguồn học thuật

- Kahn (1962), [Topological sorting of large networks](https://doi.org/10.1145/368996.369025).
- MIT 6.006, [DFS và topological sorting](https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-fall-2011/resources/mit6_006f11_lec14/).
- Pearce và Kelly (2007), [bản tác giả](https://whileydave.com/publications/PK07_JEA_preprint.pdf), đặc biệt baseline STO và cách đối chiếu công việc với thời gian. Không lấy số liệu của bài này làm số liệu của nhóm.
- [NetworkX DAG API](https://networkx.org/documentation/stable/reference/algorithms/dag.html).
- [Google Benchmark User Guide](https://github.com/google/benchmark/blob/main/docs/user_guide.md), tham khảo phương pháp khởi động và lặp; harness này tự cài, không phụ thuộc Google Benchmark.

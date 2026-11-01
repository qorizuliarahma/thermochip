# ThermoChip

**Desain *cold plate* chip semikonduktor berdaya tinggi berbasis integrasi simulasi CFD dan *machine learning***

Repositori ini berisi kode yang mengolah hasil simulasi Autodesk CFD menjadi data, model ML berbasis fisika, usulan kasus CFD berikutnya, desain teroptimasi, dan analisis tekno-ekonomi. Kode ini adalah Lampiran C proposal ThermoChip (Tim SIGMA GACOR, Universitas Pendidikan Indonesia) untuk SENO Hackathon 2026.

> **Status (1 November 2026).** Tahap desain, simulasi, dan komputasi. Satu kasus CFD dengan material sesuai rancangan (CP-01) sudah selesai dan tercatat di `data/`. Uji independensi mesh (GCI) dan 50 kasus *Latin Hypercube* sedang berjalan. Belum ada data eksperimen. Pembuatan dan uji prototipe direncanakan pada tahap lanjutan.

## Alur kerja

1. Uji independensi mesh dengan *Grid Convergence Index* (GCI).
2. Pemeriksaan neraca energi dan perbandingan hasil CFD dengan teori (bilangan Nusselt dan faktor gesek).
3. Pelatihan model ML dari data CFD. Tiga kandidat (GP, *Gradient Boosting*, dan hibrid Fisika+GP) dibandingkan dengan *repeated 5-fold cross-validation*.
4. Penjelasan model dengan SHAP.
5. Optimasi desain berkendala fabrikasi dan front Pareto.
6. Sampling adaptif: usulan sekitar 10 kasus CFD berikutnya dengan kriteria *Expected Improvement*.
7. Analisis tekno-ekonomi per rak AI.

Langkah 3–6 otomatis dilewati sampai tersedia minimal 15 kasus CFD (atur dengan `--min-ml`). Setiap fungsi mencantumkan sumber rumusnya; daftar lengkap ada di bagian [Referensi](#referensi).

## Gagasan utama: model hibrid Fisika+GP

Data CFD mahal sehingga jumlahnya sedikit. Model ML tidak dilatih dari nol: model hambatan termal (Tuckerman & Pease, 1981) menjadi dasar, dan *Gaussian Process* hanya mempelajari **selisih** CFD terhadap teori:

```
y_prediksi = model_fisika(x) + GP(x)
```

Dengan cara ini prediksi di luar titik data tetap mengikuti fisika. Kode membandingkannya secara adil dengan GP murni dan *Gradient Boosting*, lalu memilih model dengan RMSE terkecil.

## Hasil CFD yang sudah ada

| Kasus | Kondisi | T maks CFD | T maks fisika | ΔP CFD | ΔP fisika | Neraca energi |
| --- | --- | --- | --- | --- | --- | --- |
| CP-01 | Die silikon, *cold plate* Al 6061-T6, 0,963 L/menit, 300 W, 1,11 juta elemen | 51,4 °C | 53,9 °C | 677 Pa | 571 Pa | galat 0,12% |

Rincian pengaturan, cara pengambilan angka, dan catatan ada di [`docs/hasil_cfd_cp01.md`](docs/hasil_cfd_cp01.md).

## Memulai

Butuh Python 3.10 atau lebih baru.

```bash
git clone https://github.com/qorizuliarahma/thermochip.git
cd thermochip
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

Bila PowerShell menolak skrip aktivasi, jalankan `Set-ExecutionPolicy -Scope Process Bypass`, lalu ulangi.

Di VS Code, buka foldernya lewat **File → Open Folder**, lalu pilih interpreter `.venv` (**Ctrl+Shift+P → Python: Select Interpreter**). Konfigurasi siap pakai ada di menu **Run and Debug**: "Demo (data sintetis)", "Excel ke CSV (hasil CFD)", "Data CFD saya", "Data CFD saya - tembaga", "Tekno-ekonomi saja", dan "Hitung fisika CP-01".

### Uji coba dengan data demo

```bash
python run_analysis.py --demo
```

Perintah ini membuat data **sintetis** di `data_demo/` dan menjalankan seluruh alur, dengan hasil di `results_demo/` (sekitar 30–60 detik). Data demo hanya untuk memastikan kode berjalan, **jangan dipakai sebagai hasil penelitian**.

### Menjalankan dengan data CFD

```bash
python xlsx_ke_csv.py      # lembar kerja Excel -> data/cfd_results.csv dan data/mesh_study.csv
python run_analysis.py     # seluruh alur, hasil di results/
```

Pilihan lain:

```bash
python run_analysis.py --solid copper --dp-max 2000           # cold plate tembaga, chip 1.000 W
python run_analysis.py --dp-max 800 --w-min 0.5 --ar-max 8    # batas optimasi dan fabrikasi
python -m tc.tekno_ekonomi                                    # tekno-ekonomi saja
```

Secara bawaan, model fisika memakai properti air yang sama dengan material Water di Autodesk CFD (`--air autodesk`), sehingga perbandingannya dengan CFD adil. Pakai `--air konstan` untuk properti air 25 °C dari Huber dkk. (2009, 2012). Dengan data CP-01 saat ini, keluarannya adalah selisih T maks 2,50 °C dan selisih ΔP 18,6% terhadap model fisika.

### Model fisika untuk satu kasus

```bash
python hitung_fisika.py --w 1.0 --t 0.5 --H 3.0 --flow 0.9626 --material al6061 --air autodesk
```

Pakai `--air autodesk` bila CFD memakai material Water bawaan Autodesk CFD. Isi `--flow` dengan *volume flow in* dari laporan CFD (cm³/s × 0,06 = L/menit). Keluaran juga menampilkan temperatur keluar yang seharusnya, untuk mengecek neraca energi.

## Mencatat hasil CFD

Cara yang disarankan adalah lembar kerja `data/lembar_running_CFD.xlsx`:

- **Petunjuk**: geometri, material, kondisi batas, *solver*, mesh, dan cara mengambil hasil.
- **Kasus**: 53 kasus berurut prioritas (CP-01 dan CP-02 → R01–R05 → CP-03 1.000 W → R06–R50). Isi sel **kuning** setelah tiap run. Kolom *Cek* menandai run yang neraca energinya meleset lebih dari ±2% atau T maks-nya berbeda lebih dari 10 °C dari model fisika.
- **Mesh_GCI**: isian uji mesh CP-01 dengan estimasi GCI cepat.

Simpan dan tutup Excel sebelum menjalankan `xlsx_ke_csv.py`. Kasus tembaga 1.000 W dipisah dengan `python xlsx_ke_csv.py --material Tembaga --q 1000 --out data/cfd_results_tembaga.csv`.

| Kolom | Satuan | Cara mengambil di Autodesk CFD |
| --- | --- | --- |
| `T_max_cfd` | °C | Temperatur maksimum pada part die (silikon) |
| `dP_cfd` | Pa | *Inlet bulk pressure* di ringkasan (.sum), karena outlet diatur 0 Pa. Bila satuannya dyne/cm², bagi 10 |
| `T_out_cfd` | °C | Rata-rata massa: 25 + (*heat transfer from wall to fluid*) / (ṁ × c_p). Jangan pakai *outlet bulk temperature* di .sum karena itu rata-rata luas |
| `dP_channel_cfd` | Pa | Opsional: selisih tekanan bidang awal dan akhir kanal |
| `mesh_elements` | – | Jumlah elemen di ringkasan mesh |

Pemisah desimal di CSV memakai titik. Baris yang `T_max_cfd` dan `dP_cfd`-nya kosong diabaikan.

Untuk uji mesh, jalankan CP-01 pada tiga tingkat mesh dan isi `data/mesh_study.csv` (atau sheet Mesh_GCI). Jumlah elemen antartingkat sebaiknya berbeda minimal sekitar 2,2 kali.

## Hasil di `results/`

| File | Isi |
| --- | --- |
| `tabel_gci.csv` | Orde konvergensi p, nilai ekstrapolasi, GCI (%) |
| `tabel_cfd_terolah.csv` | Hambatan termal, Re, galat neraca energi, Nu dan f efektif, selisih terhadap teori dan model fisika |
| `gambar_neraca_energi.png` | Galat neraca energi tiap run (pita ±2%) |
| `gambar_teori_vs_cfd.png` | Nu dan f·Re: CFD terhadap korelasi |
| `tabel_cv_model.csv`, `gambar_parity_*.png` | Kinerja tiga model ML (validasi silang) |
| `gambar_shap_*.png` | Pengaruh tiap parameter (SHAP) |
| `tabel_pareto.csv`, `gambar_pareto.png` | Desain optimal untuk berbagai batas ΔP |
| `tabel_usulan_cfd_adaptif.csv` | Usulan kasus A01–A10 berikutnya |
| `tabel_tea_*.csv` | Penghematan energi, sensitivitas, periode pengembalian, NPV |
| `ringkasan.json` | Ringkasan angka utama |

Folder `results/` dibuat ulang setiap kali kode dijalankan dan tidak ikut disimpan di repositori.

## Siklus integrasi CFD–ML

1. Simulasikan kasus awal dari lembar kerja, lalu isi hasilnya.
2. Jalankan `python run_analysis.py`, lalu buka `results/tabel_usulan_cfd_adaptif.csv`.
3. Simulasikan kasus A01–A10 di Autodesk CFD dan tambahkan sebagai baris baru.
4. Jalankan ulang. Desain optimum di `ringkasan.json` menjadi kandidat CP-02 untuk diverifikasi CFD.

## Struktur repositori

```
thermochip/
├── run_analysis.py        alur lengkap
├── hitung_fisika.py       model fisika untuk satu kasus
├── xlsx_ke_csv.py         lembar kerja Excel -> CSV
├── make_demo_data.py      pembuat data sintetis untuk uji coba
├── tc/
│   ├── properties.py      properti air, Al 6061, tembaga, silikon (dengan sumber)
│   ├── geometry.py        geometri kanal: N, Dh, rasio sisi
│   ├── correlations.py    korelasi Shah & London, Shah, Hausen, sirip; model hambatan termal
│   ├── gci.py             prosedur GCI Celik dkk. (2008)
│   ├── cfd_post.py        pengolahan CFD dan perbandingan dengan teori
│   ├── surrogate.py       GP, GBR, hibrid Fisika+GP; validasi silang; SHAP
│   ├── optimize.py        differential evolution berkendala; front Pareto
│   ├── adaptive.py        sampling adaptif Expected Improvement
│   ├── tekno_ekonomi.py   penghematan energi, sensitivitas, pengembalian, NPV
│   └── plots.py           gambar 300 dpi berlabel bahasa Indonesia
├── data/
│   ├── lembar_running_CFD.xlsx   lembar kerja kasus CFD (sumber utama)
│   ├── cfd_results.csv           hasil CFD per kasus
│   ├── mesh_study.csv            isian uji mesh
│   └── cfd_raw/                  ringkasan asli Autodesk CFD (.sum) dan data profil kanal
├── docs/
│   ├── hasil_cfd_cp01.md         dokumentasi CFD CP-01
│   ├── referensi.bib             daftar pustaka (BibTeX, bisa diimpor ke Mendeley/Zotero)
│   └── img/                      gambar model, mesh, garis alir, dan profil kanal
├── .vscode/               konfigurasi Run and Debug
├── requirements.txt
├── CITATION.cff
└── LICENSE
```

## Tim

- Qori Zulia Rahma, Program Studi Pendidikan Teknik Mesin, Universitas Pendidikan Indonesia (ketua)
- Muhammad Rafi Atthoriq, Program Studi Pendidikan Teknik Mesin, Universitas Pendidikan Indonesia (anggota)
- Dr. Eng. Agus Setiawan, M.Si., Universitas Pendidikan Indonesia (supervisor)

Bila memakai kode ini, mohon sitasi sesuai `CITATION.cff`.

## Lisensi

Kode dirilis dengan lisensi MIT (lihat `LICENSE`).

## Referensi

1. Tuckerman, D. B., & Pease, R. F. W. (1981). High-performance heat sinking for VLSI. *IEEE Electron Device Letters*, 2(5), 126–129. https://doi.org/10.1109/EDL.1981.25367
2. Shah, R. K. (1978). A correlation for laminar hydrodynamic entry length solutions for circular and noncircular ducts. *Journal of Fluids Engineering*, 100(2), 177–179. https://doi.org/10.1115/1.3448626
3. Shah, R. K., & London, A. L. (1978). *Laminar Flow Forced Convection in Ducts*. Academic Press.
4. Qu, W., & Mudawar, I. (2002). Experimental and numerical study of pressure drop and heat transfer in a single-phase micro-channel heat sink. *International Journal of Heat and Mass Transfer*, 45(12), 2549–2565. https://doi.org/10.1016/S0017-9310(01)00337-4
5. Celik, I. B., Ghia, U., Roache, P. J., & Freitas, C. J. (2008). Procedure for estimation and reporting of uncertainty due to discretization in CFD applications. *Journal of Fluids Engineering*, 130(7), 078001. https://doi.org/10.1115/1.2960953
6. Lundberg, S. M., et al. (2020). From local explanations to global understanding with explainable AI for trees. *Nature Machine Intelligence*, 2, 56–67. https://doi.org/10.1038/s42256-019-0138-9
7. Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. *NeurIPS 30*. https://arxiv.org/abs/1705.07874
8. Friedman, J. H. (2001). Greedy function approximation: A gradient boosting machine. *Annals of Statistics*, 29(5), 1189–1232. https://doi.org/10.1214/aos/1013203451
9. McKay, M. D., Beckman, R. J., & Conover, W. J. (1979). A comparison of three methods for selecting values of input variables in the analysis of output from a computer code. *Technometrics*, 21(2), 239–245. https://doi.org/10.1080/00401706.1979.10489755
10. Sikirica, A., Grbčić, L., & Kranjčević, L. (2022). Machine learning based surrogate models for microchannel heat sink optimization. arXiv:2208.09683. https://arxiv.org/abs/2208.09683
11. Glassbrenner, C. J., & Slack, G. A. (1964). Thermal conductivity of silicon and germanium from 3°K to the melting point. *Physical Review*, 134(4A), A1058. https://doi.org/10.1103/PhysRev.134.A1058
12. Huber, M. L., et al. (2009). New international formulation for the viscosity of H₂O. *Journal of Physical and Chemical Reference Data*, 38(2), 101–125. https://doi.org/10.1063/1.3088050
13. Huber, M. L., et al. (2012). New international formulation for the thermal conductivity of H₂O. *Journal of Physical and Chemical Reference Data*, 41(3), 033102. https://doi.org/10.1063/1.4738955
14. Jones, D. R., Schonlau, M., & Welch, W. J. (1998). Efficient global optimization of expensive black-box functions. *Journal of Global Optimization*, 13(4), 455–492. https://doi.org/10.1023/A:1008306431147

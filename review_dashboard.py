from collections import Counter
from pathlib import Path
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from sentiment import Analyzer, safe_cell


class App:
    def __init__(self, root):
        self.root = root
        root.title('리뷰 감성 분석')
        root.geometry('1120x800')
        root.minsize(900, 680)
        self.analyzer = Analyzer()
        self.rows = []
        self.results = []
        self.busy = False
        self.column = tk.StringVar()
        self.status = tk.StringVar(value='한국어 감성 사전과 부정 표현 규칙으로 분석합니다. 점수는 확률이 아닙니다.')
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='리뷰 감성 분석', font=('맑은 고딕', 19, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='한 문장 분석과 CSV 일괄 분석 · 긍정 / 부정 / 중립').pack(anchor='w', pady=(4, 10))
        self.input = tk.Text(frame, height=3, font=('맑은 고딕', 11), wrap='word')
        self.input.pack(fill='x')
        self.input.insert('1.0', '배송이 빠르고 포장이 깔끔해서 만족합니다.')
        single_bar = ttk.Frame(frame)
        single_bar.pack(fill='x', pady=8)
        ttk.Button(single_bar, text='문장 분석', command=self.single).pack(side='left')
        self.single_result = tk.StringVar()
        ttk.Label(single_bar, textvariable=self.single_result, wraplength=850).pack(side='left', padx=12)
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=12)
        self.load_button = ttk.Button(bar, text='CSV 열기', command=self.open_csv)
        self.load_button.pack(side='left')
        self.sample_button = ttk.Button(bar, text='예제 리뷰', command=lambda: self.load_csv(Path(__file__).with_name('sample_reviews.csv')))
        self.sample_button.pack(side='left', padx=8)
        ttk.Label(bar, text='리뷰 열').pack(side='left', padx=(12, 4))
        self.column_box = ttk.Combobox(bar, textvariable=self.column, state='readonly', width=16)
        self.column_box.pack(side='left')
        self.run_button = ttk.Button(bar, text='전체 분석', command=self.batch)
        self.run_button.pack(side='left', padx=8)
        self.save_button = ttk.Button(bar, text='결과 CSV 저장', command=self.export)
        self.save_button.pack(side='right')
        self.chart = tk.Canvas(frame, height=90, bg='#f3f5f8', highlightthickness=0)
        self.chart.pack(fill='x', pady=(0, 12))
        self.chart.bind('<Configure>', lambda event: self.draw_chart())
        table_frame = ttk.Frame(frame)
        table_frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table_frame, columns=('label', 'score', 'text', 'reason'), show='headings')
        for key, name, width in [('label', '분류', 75), ('score', '점수', 65), ('text', '리뷰', 480), ('reason', '일치 표현', 320)]:
            self.tree.heading(key, text=name)
            self.tree.column(key, width=width, minwidth=50)
        scroll = ttk.Scrollbar(table_frame, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        for label, color in [('긍정', '#e8f5eb'), ('부정', '#fce9e9'), ('중립', '#f0f2f5'), ('분석 불가', '#fff4da')]:
            self.tree.tag_configure(label, background=color)
        self.tree.bind('<Double-Button-1>', self.detail)
        ttk.Label(frame, textvariable=self.status, wraplength=1000).pack(fill='x', pady=(12, 0))
        self.single()
        self.load_csv(Path(__file__).with_name('sample_reviews.csv'))
        self.batch()

    def single(self):
        result = self.analyzer.analyze(self.input.get('1.0', 'end'))
        self.single_result.set(f"{result['label']} · {result['score']:+.2f} · {result['reason']}")

    def open_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV', '*.csv')])
        if path:
            self.load_csv(path)

    def load_csv(self, path):
        if self.busy:
            return
        try:
            rows = None
            for encoding in ('utf-8-sig', 'cp949'):
                try:
                    with open(path, encoding=encoding, newline='') as file:
                        reader = csv.DictReader(file)
                        fields = reader.fieldnames
                        if not fields or any(not field for field in fields) or len(set(fields)) != len(fields):
                            raise ValueError('첫 행에 중복되지 않는 열 이름이 필요합니다.')
                        candidate_rows = []
                        for row in reader:
                            if len(candidate_rows) >= 50000:
                                raise ValueError('한 번에 최대 50,000행까지 분석할 수 있습니다.')
                            if None in row:
                                raise ValueError('열 수가 맞지 않는 행이 있습니다. 쉼표가 포함된 리뷰는 큰따옴표로 감싸 주세요.')
                            candidate_rows.append(row)
                    rows = candidate_rows
                    break
                except UnicodeDecodeError:
                    continue
            if rows is None:
                raise ValueError('UTF-8 또는 CP949 형식으로 저장한 CSV를 사용하세요.')
            self.rows = rows
            self.fields = fields
            self.column_box.configure(values=fields)
            self.column.set(next((field for field in fields if field.lower() in ('review', 'text', 'content', '리뷰', '내용')), fields[0]))
            self.results = []
            self.tree.delete(*self.tree.get_children())
            self.draw_chart()
            self.status.set(f'{Path(path).name} · {len(rows):,}행 · 리뷰 열을 확인하고 전체 분석을 누르세요.')
        except (OSError, ValueError, csv.Error) as exc:
            messagebox.showerror('CSV 불러오기 실패', str(exc))

    def batch(self):
        if self.busy:
            return
        if not self.rows:
            messagebox.showinfo('분석', '분석할 CSV 행이 없습니다.')
            return
        self.busy = True
        self.results = []
        self.analysis_column = self.column.get()
        self.tree.delete(*self.tree.get_children())
        for button in (self.load_button, self.sample_button, self.run_button, self.save_button):
            button.configure(state='disabled')
        self.column_box.configure(state='disabled')
        self.process(0)

    def process(self, start):
        end = min(start+200, len(self.rows))
        for index in range(start, end):
            text = self.rows[index].get(self.analysis_column) or ''
            result = self.analyzer.analyze(text)
            result['text'] = text
            self.results.append(result)
            if index < 3000:
                self.tree.insert('', 'end', iid=str(index), values=(result['label'], f"{result['score']:+.2f}", text, result['reason']), tags=(result['label'],))
        self.status.set(f'분석 중 · {end:,} / {len(self.rows):,}')
        if end < len(self.rows):
            self.root.after(1, lambda: self.process(end))
        else:
            self.busy = False
            for button in (self.load_button, self.sample_button, self.run_button, self.save_button):
                button.configure(state='normal')
            self.column_box.configure(state='readonly')
            self.draw_chart()
            self.status.set(f'{len(self.results):,}행 분석 완료 · 표는 최대 3,000행 표시, CSV는 전체 저장 · 사전 기반 결과이며 반어법·복잡한 문장은 오분류할 수 있습니다.')

    def draw_chart(self):
        self.chart.delete('all')
        counts = Counter(row['label'] for row in self.results)
        total = len(self.results)
        width = max(200, self.chart.winfo_width())-30
        x = 15
        colors = {'긍정': '#419466', '부정': '#d76b6b', '중립': '#8593a6', '분석 불가': '#d6ae54'}
        for label, color in colors.items():
            fraction = counts[label]/total if total else 0
            if fraction:
                self.chart.create_rectangle(x, 15, x+width*fraction, 40, fill=color, outline='')
                x += width*fraction
        self.chart.create_text(15, 65, anchor='w', font=('맑은 고딕', 10), text='    '.join(f'{label} {counts[label]:,}개 ({counts[label]/total:.0%})' if total else f'{label} 0개' for label in colors))

    def detail(self, event=None):
        selected = self.tree.selection()
        if selected:
            row = self.results[int(selected[0])]
            messagebox.showinfo(f"{row['label']} / {row['score']:+.2f}", f"{row['text']}\n\n일치 표현: {row['reason']}")

    def export(self):
        if not self.results or self.busy:
            messagebox.showinfo('저장', 'CSV 전체 분석을 먼저 완료하세요.')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='review_results.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        try:
            extra = []
            for name in ('sentiment', 'sentiment_score', 'matched_terms'):
                while name in self.fields or name in extra:
                    name += '_result'
                extra.append(name)
            with open(path, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([safe_cell(field) for field in self.fields+extra])
                for source, result in zip(self.rows, self.results):
                    values = [safe_cell(source.get(field) or '') for field in self.fields]
                    writer.writerow(values+[result['label'], result['score'], safe_cell(result['reason'])])
            self.status.set(f'{len(self.results):,}행 저장 완료 · {Path(path).name}')
        except OSError as exc:
            messagebox.showerror('저장 실패', str(exc))


if __name__ == '__main__':
    root = tk.Tk()
    ttk.Style().configure('.', font=('맑은 고딕', 10))
    App(root)
    root.mainloop()

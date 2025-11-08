#!/usr/bin/env python3
"""
Автоматизированный скрипт для запуска Locust тестов и извлечения статистики.
Запускает все конфигурации логирования и собирает результаты в читаемом формате.

Usage:
    python run_benchmarks.py
    
Requirements:
    - FastAPI server running on http://127.0.0.1:8000
    - locust installed (pip install locust)
    - locustfile.py in the same directory
"""

import subprocess
import time
import csv
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


class LocustBenchmark:
    def __init__(
        self,
        locustfile: str = "locustfile.py",
        host: str = "http://127.0.0.1:8000",
        users: int = 50,
        spawn_rate: int = 10,
        run_time: str = "5m",
    ):
        self.locustfile = locustfile
        self.host = host
        self.users = users
        self.spawn_rate = spawn_rate
        self.run_time = run_time
        
        # Конфигурации для тестирования
        self.tags = [
            "baseline",
            "logs",
            "aiologger",
            "aiologger-await",
            "custom-async",
            "custom-async-await",
        ]
        
        # Количество логов для тестирования
        self.log_volumes = [100, 400]
    
    def run_locust_test(
        self, tag: str, csv_prefix: str
    ) -> Tuple[bool, str]:
        """
        Запускает один Locust тест с указанным тегом.
        
        Args:
            tag: Тег endpoint'а для тестирования
            csv_prefix: Префикс для CSV файлов
            
        Returns:
            Tuple[success, error_message]
        """
        cmd = [
            "locust",
            "-f", self.locustfile,
            "--headless",
            "-u", str(self.users),
            "-r", str(self.spawn_rate),
            "-t", self.run_time,
            "--tag", tag,
            "--host", self.host,
            "--csv", csv_prefix,
            "--only-summary",  # Только итоговая статистика
        ]
        
        print(f"\n{'='*80}")
        print(f"Running test: {tag}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*80}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=400,  # 6+ минут таймаут
            )
            
            if result.returncode != 0:
                return False, result.stderr
            
            return True, ""
            
        except subprocess.TimeoutExpired:
            return False, "Test timeout exceeded"
        except Exception as e:
            return False, str(e)
    
    def parse_stats_csv(self, csv_file: str) -> Dict[str, float]:
        """
        Парсит _stats.csv файл и извлекает агрегированную статистику.
        
        Args:
            csv_file: Путь к CSV файлу со статистикой
            
        Returns:
            Dictionary с метриками: min, median, avg, max
        """
        if not os.path.exists(csv_file):
            print(f"Warning: CSV file not found: {csv_file}")
            return {}
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
                # Ищем агрегированную строку (Aggregated)
                agg_row = None
                for row in rows:
                    if row.get('Name') == 'Aggregated' or row.get('Type') == 'Aggregated':
                        agg_row = row
                        break
                
                if not agg_row:
                    # Если нет Aggregated, берем последнюю строку
                    agg_row = rows[-1] if rows else {}
                
                # Извлекаем метрики (в миллисекундах)
                return {
                    'min': float(agg_row.get('Min Response Time', 0)),
                    'median': float(agg_row.get('Median Response Time', 0)),
                    'avg': float(agg_row.get('Average Response Time', 0)),
                    'max': float(agg_row.get('Max Response Time', 0)),
                    'rps': float(agg_row.get('Requests/s', 0)),
                    'failures': int(agg_row.get('Failure Count', 0)),
                }
        except Exception as e:
            print(f"Error parsing CSV {csv_file}: {e}")
            return {}
    
    def format_stats(self, stats: Dict[str, float]) -> str:
        """
        Форматирует статистику в читаемый формат: min-median-avg-max
        
        Args:
            stats: Dictionary с метриками
            
        Returns:
            Форматированная строка вида "3-27-29-80"
        """
        if not stats:
            return "N/A"
        
        return f"{int(stats['min'])}-{int(stats['median'])}-{int(stats['avg'])}-{int(stats['max'])}"
    
    def update_locustfile_n_logs(self, n_logs: int):
        """
        Обновляет значение N_LOGS в locustfile.py
        
        Args:
            n_logs: Новое значение для N_LOGS
        """
        try:
            with open(self.locustfile, 'r') as f:
                content = f.read()
            
            # Ищем и заменяем N_LOGS
            import re
            pattern = r'N_LOGS\s*=\s*\d+'
            replacement = f'N_LOGS = {n_logs}'
            
            new_content = re.sub(pattern, replacement, content)
            
            with open(self.locustfile, 'w') as f:
                f.write(new_content)
            
            print(f"Updated {self.locustfile}: N_LOGS = {n_logs}")
            
        except Exception as e:
            print(f"Error updating locustfile: {e}")
            sys.exit(1)
    
    def run_all_tests(self):
        """
        Запускает все тесты для всех конфигураций и объемов логов.
        """
        results = {}
        
        for n_logs in self.log_volumes:
            print(f"\n\n{'#'*80}")
            print(f"# Testing with {n_logs} logs/endpoint")
            print(f"{'#'*80}\n")
            
            # Обновляем N_LOGS в locustfile
            self.update_locustfile_n_logs(n_logs)
            
            # Даем серверу время на стабилизацию
            time.sleep(2)
            
            results[n_logs] = {}
            
            for tag in self.tags:
                csv_prefix = f"results/{n_logs}logs_{tag}"
                
                # Создаем директорию для результатов
                Path("results").mkdir(exist_ok=True)
                
                # Запускаем тест
                success, error = self.run_locust_test(tag, csv_prefix)
                
                if not success:
                    print(f"❌ Test failed: {error}")
                    results[n_logs][tag] = None
                    continue
                
                # Даем время на запись CSV
                time.sleep(1)
                
                # Парсим результаты
                stats_file = f"{csv_prefix}_stats.csv"
                stats = self.parse_stats_csv(stats_file)
                
                if stats:
                    results[n_logs][tag] = stats
                    print(f"✅ Test completed: {self.format_stats(stats)}")
                else:
                    results[n_logs][tag] = None
                    print(f"⚠️  Failed to parse results")
                
                # Пауза между тестами
                print(f"Waiting 5 seconds before next test...")
                time.sleep(5)
        
        return results
    
    def print_summary(self, results: Dict):
        """
        Выводит итоговую статистику в читаемом формате.
        
        Args:
            results: Dictionary с результатами всех тестов
        """
        print(f"\n\n{'='*80}")
        print("BENCHMARK RESULTS")
        print(f"{'='*80}\n")
        
        for n_logs, tags_results in sorted(results.items()):
            print(f"\n{n_logs} logs/endpoint # min - median - avg - max, ms/request\n")
            
            for tag in self.tags:
                stats = tags_results.get(tag)
                if stats:
                    formatted = self.format_stats(stats)
                    rps = stats.get('rps', 0)
                    failures = stats.get('failures', 0)
                    
                    status = "✅" if failures == 0 else "❌"
                    print(f"{status} {rps:.1f} RPS {tag:20s}: {formatted}")
                else:
                    print(f"❌ N/A RPS {tag:20s}: FAILED")
            
            # Находим лучший результат
            valid_results = {
                tag: stats for tag, stats in tags_results.items() 
                if stats and tag != 'baseline'
            }
            
            if valid_results:
                best_tag = min(
                    valid_results.keys(), 
                    key=lambda t: valid_results[t]['avg']
                )
                best_avg = valid_results[best_tag]['avg']
                baseline_avg = tags_results.get('baseline', {}).get('avg', 0)
                
                if baseline_avg:
                    overhead = ((best_avg - baseline_avg) / baseline_avg) * 100
                    print(f"\n🏆 Best: {best_tag} (overhead: +{overhead:.1f}%)")
        
        print(f"\n{'='*80}")
        print("Notes:")
        print("- baseline: no logging")
        print("- lower is better")
        print("- check for failures (❌)")
        print(f"{'='*80}\n")


def main():
    """Main entry point."""
    
    # Проверяем, что сервер запущен
    print("Checking if FastAPI server is running...")
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8000))
    sock.close()
    
    if result != 0:
        print("❌ Error: FastAPI server is not running on http://127.0.0.1:8000")
        print("Please start the server with: python main.py")
        sys.exit(1)
    
    print("✅ Server is running\n")
    
    # Создаем benchmark runner
    benchmark = LocustBenchmark()
    
    # Запускаем все тесты
    results = benchmark.run_all_tests()
    
    # Выводим итоговую статистику
    benchmark.print_summary(results)
    
    print("\nDone! Results saved in ./results/ directory")


if __name__ == "__main__":
    main()
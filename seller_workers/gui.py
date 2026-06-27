"""GUI local para ligar e desligar executores."""

from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any, Callable

from supabase import Client

from seller_workers.config import (
    Config,
    carregar_config_permissiva,
    config_supabase_completa,
    salvar_config_supabase,
)
from seller_workers.database import autenticar_cliente_supabase, sair_cliente_supabase
from seller_workers.executors.executor_1_vitrines import rodar_ciclo_executor_1
from seller_workers.executors.executor_2_produtos import rodar_ciclo_executor_2
from seller_workers.executors.executor_3_teste_seller import rodar_ciclo_executor_3
from seller_workers.executors.executor_4_produtos import rodar_ciclo_executor_4
from seller_workers.seller_session import SellerSession

LogFn = Callable[[str], None]
StopFn = Callable[[], bool]
DriverFn = Callable[[Any | None], None]
SellerDriverFn = Callable[[], Any | None]
ExecutorFn = Callable[[Config, Client, LogFn, StopFn, DriverFn, SellerDriverFn], int]
SupabaseClientFn = Callable[[], Client | None]


@dataclass(frozen=True)
class ExecutorDef:
    chave: str
    nome: str
    habilitado_inicialmente: bool
    rodar_ciclo: ExecutorFn


class ExecutorController:
    def __init__(
        self,
        executor: ExecutorDef,
        config: Config,
        log_queue: queue.Queue[str],
        on_status_change: Callable[[], None],
        get_supabase_client: SupabaseClientFn,
        get_seller_driver: SellerDriverFn,
    ) -> None:
        self.executor = executor
        self.config = config
        self.log_queue = log_queue
        self.on_status_change = on_status_change
        self.get_supabase_client = get_supabase_client
        self.get_seller_driver = get_seller_driver
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.current_driver: Any | None = None
        self.status = "desligado"
        self.proxima_execucao = "-"

    def ligar(self) -> None:
        if self.get_supabase_client() is None:
            self.log(f"{self.executor.nome}: conecte no Supabase antes de ligar.")
            return

        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.status = "ligado"
        self.proxima_execucao = "agora"
        self.on_status_change()
        self.log(f"{self.executor.nome}: ligado.")

    def desligar(self) -> None:
        if not self.thread or not self.thread.is_alive():
            self.status = "desligado"
            self.proxima_execucao = "-"
            self.on_status_change()
            return

        self.stop_event.set()
        self.status = "parando"
        self.proxima_execucao = "-"
        self.on_status_change()
        self.log(f"{self.executor.nome}: desligamento solicitado.")
        self._fechar_driver_ativo()

    def log(self, mensagem: str) -> None:
        horario = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{horario}] {mensagem}")

    def registrar_driver(self, driver: Any | None) -> None:
        self.current_driver = driver

    def _fechar_driver_ativo(self) -> None:
        if not self.current_driver:
            return

        try:
            self.current_driver.quit()
            self.log(f"{self.executor.nome}: Selenium fechado pelo botao Desligar.")
        except Exception as exc:
            self.log(f"{self.executor.nome}: erro ao fechar Selenium: {exc}")
        finally:
            self.current_driver = None

    def _loop(self) -> None:
        try:
            supabase = self.get_supabase_client()
            if supabase is None:
                self.log(f"{self.executor.nome}: sem sessao Supabase autenticada.")
                return

            while not self.stop_event.is_set():
                self.status = "executando"
                self.proxima_execucao = "em execucao"
                self.on_status_change()

                try:
                    intervalo = self.executor.rodar_ciclo(
                        self.config,
                        supabase,
                        self.log,
                        self.stop_event.is_set,
                        self.registrar_driver,
                        self.get_seller_driver,
                    )
                except Exception as exc:
                    intervalo = self.config.intervalo_orquestrador_segundos
                    self.log(f"{self.executor.nome}: erro no ciclo: {exc}")

                if self.stop_event.is_set():
                    break

                self.status = "aguardando"
                self.proxima_execucao = f"{intervalo}s"
                self.on_status_change()
                self.log(f"{self.executor.nome}: proximo ciclo em {intervalo}s.")
                self.stop_event.wait(intervalo)

        finally:
            self.status = "desligado"
            self.proxima_execucao = "-"
            self.on_status_change()
            self.log(f"{self.executor.nome}: desligado.")


class SellerCentralApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OpSeller Agent")
        self.geometry("860x560")
        self.minsize(760, 480)

        self.log_queue: queue.Queue[str] = queue.Queue()

        self.config = carregar_config_permissiva()

        self.seller_session = SellerSession(self.config, self._log_gui)
        self.controllers: list[ExecutorController] = []
        self.status_vars: dict[str, tk.StringVar] = {}
        self.proxima_execucao_vars: dict[str, tk.StringVar] = {}
        self.ligar_buttons: dict[str, ttk.Button] = {}
        self.executores_frame: ttk.LabelFrame | None = None
        self.supabase_client: Client | None = None
        self.config_status_var = tk.StringVar(value="")
        self.config_supabase_url_var = tk.StringVar(value=self.config.supabase_url)
        self.config_supabase_key_var = tk.StringVar(value=self.config.supabase_key)
        self.supabase_status_var = tk.StringVar(value="Status: desconectado")
        self.supabase_email_var = tk.StringVar()
        self.supabase_senha_var = tk.StringVar()
        self.seller_status_var = tk.StringVar(value="Status: fechado")

        self._montar_interface()
        self._aplicar_estado_inicial()
        self._processar_logs()
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _criar_controllers(self) -> list[ExecutorController]:
        executores = [
            ExecutorDef(
                chave="executor_1",
                nome="Executor 1 - Captura de Vitrines",
                habilitado_inicialmente=self.config.executor_1_vitrines_enabled,
                rodar_ciclo=rodar_ciclo_executor_1,
            ),
            ExecutorDef(
                chave="executor_2",
                nome="Executor 2 - Captura de Produtos",
                habilitado_inicialmente=self.config.executor_2_produtos_enabled,
                rodar_ciclo=rodar_ciclo_executor_2,
            ),
            ExecutorDef(
                chave="executor_3",
                nome="Executor 3 - Teste Seller",
                habilitado_inicialmente=self.config.executor_3_teste_seller_enabled,
                rodar_ciclo=rodar_ciclo_executor_3,
            ),
            ExecutorDef(
                chave="executor_4",
                nome="Executor 4 - Enriquecimento de Produtos",
                habilitado_inicialmente=self.config.executor_4_produtos_enabled,
                rodar_ciclo=rodar_ciclo_executor_4,
            ),
        ]

        return [
            ExecutorController(
                executor=executor,
                config=self.config,
                log_queue=self.log_queue,
                on_status_change=self._agendar_atualizacao_status,
                get_supabase_client=self._get_supabase_client,
                get_seller_driver=self._get_seller_driver,
            )
            for executor in executores
        ]

    def _get_supabase_client(self) -> Client | None:
        return self.supabase_client

    def _get_seller_driver(self) -> Any | None:
        if not self.seller_session.aberta:
            return None

        return self.seller_session.driver

    def _montar_interface(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        titulo = ttk.Label(header, text="OpSeller Agent", font=("Segoe UI", 16, "bold"))
        titulo.grid(row=0, column=0, sticky="w")

        subtitulo = ttk.Label(header, text="Ligue e desligue executores locais que consultam o Supabase e acionam workers.")
        subtitulo.grid(row=1, column=0, sticky="w", pady=(4, 0))

        corpo = ttk.Frame(self, padding=(16, 0, 16, 16))
        corpo.grid(row=1, column=0, sticky="nsew")
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(4, weight=1)

        config_frame = ttk.LabelFrame(corpo, text="Configuracao inicial", padding=12)
        config_frame.grid(row=0, column=0, sticky="ew")
        config_frame.columnconfigure(1, weight=1)

        ttk.Label(config_frame, text="Supabase URL").grid(row=0, column=0, sticky="w", padx=(0, 8))
        supabase_url = ttk.Entry(
            config_frame,
            textvariable=self.config_supabase_url_var,
        )
        supabase_url.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(config_frame, text="Publishable key").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        supabase_key = ttk.Entry(
            config_frame,
            textvariable=self.config_supabase_key_var,
            show="*",
        )
        supabase_key.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(8, 0))

        salvar_config = ttk.Button(
            config_frame,
            text="Salvar configuracao",
            command=self._salvar_configuracao_inicial,
        )
        salvar_config.grid(row=0, column=2, rowspan=2, sticky="ns")

        config_status = ttk.Label(config_frame, textvariable=self.config_status_var)
        config_status.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        supabase_frame = ttk.LabelFrame(corpo, text="Supabase", padding=12)
        supabase_frame.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        supabase_frame.columnconfigure(1, weight=1)
        supabase_frame.columnconfigure(3, weight=1)

        ttk.Label(supabase_frame, text="Email").grid(row=0, column=0, sticky="w", padx=(0, 8))
        email_entry = ttk.Entry(supabase_frame, textvariable=self.supabase_email_var)
        email_entry.grid(row=0, column=1, sticky="ew", padx=(0, 12))

        ttk.Label(supabase_frame, text="Senha").grid(row=0, column=2, sticky="w", padx=(0, 8))
        senha_entry = ttk.Entry(
            supabase_frame,
            textvariable=self.supabase_senha_var,
            show="*",
        )
        senha_entry.grid(row=0, column=3, sticky="ew", padx=(0, 12))

        conectar = ttk.Button(
            supabase_frame,
            text="Conectar",
            command=self._conectar_supabase,
        )
        conectar.grid(row=0, column=4, padx=(0, 8))

        desconectar = ttk.Button(
            supabase_frame,
            text="Desconectar",
            command=self._desconectar_supabase,
        )
        desconectar.grid(row=0, column=5)

        supabase_status = ttk.Label(supabase_frame, textvariable=self.supabase_status_var)
        supabase_status.grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        self.executores_frame = ttk.LabelFrame(corpo, text="Executores", padding=12)
        self.executores_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        self.executores_frame.columnconfigure(1, weight=1)

        self._remontar_controllers()

        seller_frame = ttk.LabelFrame(corpo, text="Sessao Seller", padding=12)
        seller_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        seller_frame.columnconfigure(1, weight=1)

        seller_nome = ttk.Label(
            seller_frame,
            text="Seller Central autenticado",
            font=("Segoe UI", 10, "bold"),
        )
        seller_nome.grid(row=0, column=0, sticky="w", padx=(0, 16))

        seller_status = ttk.Label(seller_frame, textvariable=self.seller_status_var)
        seller_status.grid(row=0, column=1, sticky="w", padx=(0, 16))

        abrir_seller = ttk.Button(
            seller_frame,
            text="Abrir/Login",
            command=self._abrir_sessao_seller,
        )
        abrir_seller.grid(row=0, column=2, padx=(0, 8))

        fechar_seller = ttk.Button(
            seller_frame,
            text="Fechar",
            command=self._fechar_sessao_seller,
        )
        fechar_seller.grid(row=0, column=3)

        logs_frame = ttk.LabelFrame(corpo, text="Logs", padding=8)
        logs_frame.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)

        self.logs_text = tk.Text(logs_frame, height=16, wrap="word", state="disabled")
        self.logs_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.logs_text.configure(yscrollcommand=scrollbar.set)

    def _montar_linha_executor(
        self,
        parent: ttk.Frame,
        controller: ExecutorController,
        row: int,
    ) -> None:
        nome = ttk.Label(parent, text=controller.executor.nome, font=("Segoe UI", 10, "bold"))
        nome.grid(row=row, column=0, sticky="w", padx=(0, 16), pady=6)

        status_var = tk.StringVar(value=controller.status)
        proxima_var = tk.StringVar(value=controller.proxima_execucao)
        self.status_vars[controller.executor.chave] = status_var
        self.proxima_execucao_vars[controller.executor.chave] = proxima_var

        status = ttk.Label(parent, textvariable=status_var)
        status.grid(row=row, column=1, sticky="w", padx=(0, 16))

        proxima = ttk.Label(parent, textvariable=proxima_var)
        proxima.grid(row=row, column=2, sticky="w", padx=(0, 16))

        ligar = ttk.Button(parent, text="Ligar", command=controller.ligar)
        ligar.grid(row=row, column=3, padx=(0, 8))
        self.ligar_buttons[controller.executor.chave] = ligar

        desligar = ttk.Button(parent, text="Desligar", command=controller.desligar)
        desligar.grid(row=row, column=4)

    def _aplicar_estado_inicial(self) -> None:
        if config_supabase_completa(self.config):
            self.config_status_var.set("Configuracao Supabase salva.")
        else:
            self.config_status_var.set(
                "Informe SUPABASE_URL e SUPABASE_KEY para liberar o login."
            )

        self._atualizar_estado_botoes_executores()

        for controller in self.controllers:
            if controller.executor.habilitado_inicialmente:
                controller.ligar()
            else:
                controller.log(f"{controller.executor.nome}: inicia desligado.")

    def _log_gui(self, mensagem: str) -> None:
        horario = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{horario}] {mensagem}")

    def _salvar_configuracao_inicial(self) -> None:
        try:
            self.config = salvar_config_supabase(
                self.config_supabase_url_var.get(),
                self.config_supabase_key_var.get(),
            )
            self.seller_session = SellerSession(self.config, self._log_gui)
            self._remontar_controllers()
            self.supabase_client = None
            self.supabase_status_var.set("Status: desconectado")
            self.config_status_var.set("Configuracao salva. Agora faca login no Supabase.")
            self._atualizar_estado_botoes_executores()
            self._log_gui("Configuracao Supabase salva no .env.")
        except Exception as exc:
            messagebox.showerror("Configuracao invalida", str(exc))

    def _remontar_controllers(self) -> None:
        for controller in self.controllers:
            controller.desligar()

        self.controllers = self._criar_controllers()
        self.status_vars.clear()
        self.proxima_execucao_vars.clear()
        self.ligar_buttons.clear()

        if self.executores_frame is None:
            return

        for widget in self.executores_frame.winfo_children():
            widget.destroy()

        for indice, controller in enumerate(self.controllers):
            self._montar_linha_executor(self.executores_frame, controller, indice)

        self._atualizar_estado_botoes_executores()

    def _conectar_supabase(self) -> None:
        if not config_supabase_completa(self.config):
            messagebox.showwarning(
                "Configuracao Supabase",
                "Salve SUPABASE_URL e SUPABASE_KEY antes de conectar.",
            )
            return

        email = self.supabase_email_var.get().strip()
        senha = self.supabase_senha_var.get()

        if not email or not senha:
            messagebox.showwarning(
                "Login Supabase",
                "Informe email e senha do usuario criado no Supabase Auth.",
            )
            return

        self.supabase_status_var.set("Status: conectando")
        self._atualizar_estado_botoes_executores()

        def conectar() -> None:
            try:
                cliente, email_usuario = autenticar_cliente_supabase(
                    self.config,
                    email,
                    senha,
                )
                self.supabase_client = cliente
                self._log_gui(f"Supabase autenticado como {email_usuario}.")
                self.after(
                    0,
                    lambda: (
                        self.supabase_senha_var.set(""),
                        self.supabase_status_var.set(
                            f"Status: conectado ({email_usuario})"
                        ),
                    ),
                )
            except Exception as exc:
                self.supabase_client = None
                self._log_gui(f"Erro ao autenticar Supabase: {exc}")
                self.after(0, lambda: self.supabase_status_var.set("Status: erro"))
            finally:
                self.after(0, self._atualizar_estado_botoes_executores)

        threading.Thread(target=conectar, daemon=True).start()

    def _desconectar_supabase(self) -> None:
        for controller in self.controllers:
            controller.desligar()

        try:
            sair_cliente_supabase(self.supabase_client)
        except Exception as exc:
            self._log_gui(f"Erro ao desconectar Supabase: {exc}")
        finally:
            self.supabase_client = None
            self.supabase_status_var.set("Status: desconectado")
            self._atualizar_estado_botoes_executores()
            self._log_gui("Supabase desconectado.")

    def _atualizar_estado_botoes_executores(self) -> None:
        estado = "normal" if self.supabase_client is not None else "disabled"
        for botao in self.ligar_buttons.values():
            botao.configure(state=estado)

    def _abrir_sessao_seller(self) -> None:
        self.seller_status_var.set("Status: abrindo")

        def abrir() -> None:
            try:
                self.seller_session.abrir()
                self.after(0, lambda: self.seller_status_var.set("Status: aberto"))
            except Exception as exc:
                self._log_gui(f"Erro ao abrir Seller Central: {exc}")
                self.after(0, lambda: self.seller_status_var.set("Status: erro"))

        threading.Thread(target=abrir, daemon=True).start()

    def _fechar_sessao_seller(self) -> None:
        self.seller_session.fechar()
        self.seller_status_var.set("Status: fechado")

    def _agendar_atualizacao_status(self) -> None:
        self.after(0, self._atualizar_status)

    def _atualizar_status(self) -> None:
        for controller in self.controllers:
            chave = controller.executor.chave
            self.status_vars[chave].set(f"Status: {controller.status}")
            self.proxima_execucao_vars[chave].set(f"Proximo ciclo: {controller.proxima_execucao}")

    def _processar_logs(self) -> None:
        while True:
            try:
                mensagem = self.log_queue.get_nowait()
            except queue.Empty:
                break

            self.logs_text.configure(state="normal")
            self.logs_text.insert("end", mensagem + "\n")
            self.logs_text.see("end")
            self.logs_text.configure(state="disabled")

        self.after(250, self._processar_logs)

    def _fechar(self) -> None:
        for controller in self.controllers:
            controller.desligar()

        try:
            sair_cliente_supabase(self.supabase_client)
        except Exception:
            pass

        self.seller_session.fechar()
        self.destroy()


def iniciar_gui() -> None:
    app = SellerCentralApp()
    app.mainloop()

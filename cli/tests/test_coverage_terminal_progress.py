"""Visual terminal components and progress indicators under empty, busy and failure states."""
from contextlib import nullcontext
from io import StringIO
from unittest.mock import MagicMock
import pytest
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from webops_cli.ui import terminal as term
from webops_cli.ui import progress as progress

@pytest.fixture
def ui():
    component=term.TerminalUI()
    component.console=Console(file=StringIO(),force_terminal=False,width=120)
    return component

@pytest.mark.parametrize("stressed", [True,False])
def test_dashboard_layout_and_system_pressure(ui,stressed):
    panel=ui.create_status_dashboard(
        {"cpu_usage":93 if stressed else 12,
         "memory_usage":95 if stressed else 20,
         "disk_usage":91 if stressed else 10,
         "uptime":"4 days", "load_avg":"0.2"},
        [{"name":"api","status":"running","health":"healthy","domain":"example.org"},
         {"name":"worker","status":"failed","health":"unhealthy"}],
        [{"name":"webops-web","status":"active","pid":123,"memory":"250 MiB"},
         {"name":"webops-beat","status":"failed"}])
    assert isinstance(panel, Layout)
    assert panel["system"].renderable.border_style==("yellow" if stressed else "green")
    assert panel["deployments"].renderable.title=="Deployments (2)"
    assert panel["services"].renderable.title=="Services"

@pytest.mark.parametrize("deployments", [[],[{"name":"service","status":"pending","health":"unknown"}],
                                          [{"name":str(i),"status":"running","health":"healthy"} for i in range(15)]])
def test_deployment_panel_empty_filled_and_truncation(ui,deployments):
    p=ui._create_deployments_panel(deployments)
    assert isinstance(p,Panel)
    if deployments: assert p.title==f"Deployments ({len(deployments)})"
    else: assert p.title=="Deployments"

@pytest.mark.parametrize("status,color",[
    ("running","green"),("active","green"),("stopped","red"),("inactive","red"),
    ("failed","bold red"),("building","yellow"),("pending","blue"),
    ("unknown","dim"),("other","white"),("RUNNING","green")
])
def test_status_colors_have_safe_unknown_fallback(ui,status,color):
    assert ui._get_status_color(status)==color

@pytest.mark.parametrize("health,color",[
    ("healthy","green"),("unhealthy","red"),("degraded","yellow"),
    ("unknown","dim"),("other","white"),("HEALTHY","green")
])
def test_health_colors_have_safe_unknown_fallback(ui,health,color):
    assert ui._get_health_color(health)==color

@pytest.mark.parametrize("description", [None, "Choose a deployment"])
def test_interactive_menu_renders_descriptions(ui,description):
    panel=ui.create_interactive_menu("Choose", [("1","Start"),("2","Stop")],description)
    assert isinstance(panel,Panel)
    assert panel.title=="Choose"

@pytest.mark.parametrize("position", [0,1,2,4])
def test_progress_indicator_past_current_and_future(ui,position):
    assert ui.display_progress_with_steps(["plan","build","verify"],position).title==f"Progress ({position+1}/3)"

@pytest.mark.parametrize("logs",[
    [],["ERROR failed","WARNING high usage","INFO starting","DEBUG details","plain"],
    ["CRITICAL stopped","WARN timeout","normal"],
    ["INFO log"]*35,
])
def test_log_viewer_coloring_empty_and_latest_lines(ui,logs):
    p=ui.create_log_viewer(logs,title="WebOps Logs",max_lines=8)
    assert isinstance(p,Panel)
    assert p.title=="WebOps Logs" if not logs else "showing last" in p.title

def test_services_with_optional_pid_memory_metadata(ui):
    p=ui._create_services_panel([
        {"name":"db","status":"active","pid":1,"memory":"512M"},
        {"name":"worker","status":"stopped"},
        {"name":"unrated"}])
    assert isinstance(p,Panel)


@pytest.fixture
def prog(monkeypatch):
    p=MagicMock()
    p.__enter__.return_value=p
    monkeypatch.setattr(progress,"Progress",lambda *args,**kwargs:p)
    monkeypatch.setattr(progress.time,"sleep",lambda *_:None)
    pm=progress.ProgressManager()
    pm.console=MagicMock()
    return pm,p

@pytest.mark.parametrize("show_pct,show_time",[(True,True),(True,False),(False,True),(False,False)])
def test_progress_bar_all_optional_column_sets(prog,show_pct,show_time):
    pm,p=prog
    with pm.progress_bar("Demo",show_percentage=show_pct,show_time=show_time) as current:
        assert current is p
    p.__enter__.assert_called()

def test_spinner_context_and_multi_progress(prog):
    pm,p=prog
    status=MagicMock()
    pm.console.status.return_value=status
    status.__enter__.return_value=status
    with pm.spinner("Loading") as current: assert current is status
    with pm.multi_progress("Deploying") as current: assert current is p

@pytest.mark.parametrize("items", [[],["checkout"],["fetch","build","health"]])
def test_deployment_and_backup_progress_nonblocking(prog,items):
    pm,p=prog
    pm.show_deployment_progress("staging",items)
    pm.show_backup_progress("db",items)
    assert p.add_task.call_count==2
    assert p.advance.call_count==2*len(items)

@pytest.mark.parametrize("statuses",[
    {"database":True,"redis":True},
    {"database":False,"redis":True},
    {"database":False,"redis":False},
])
def test_health_progress_records_all_outcomes(prog,statuses):
    pm,p=prog
    fns={name:(lambda v=value: v) for name,value in statuses.items()}
    assert pm.show_health_check_progress(fns)==statuses
    assert p.advance.call_count==len(statuses)

def test_health_progress_catches_probe_failure(prog):
    pm,p=prog
    def error(): raise ConnectionError("service unavailable")
    assert pm.show_health_check_progress({"redis":error,"db":lambda:True})=={"redis":False,"db":True}

@pytest.mark.parametrize("services",[
    {}, {"web":{"status":"active"}}, {"worker":{"status":"inactive"}},
    {"queue":{"status":"failed"}},{"proxy":{"status":"unknown"}},
])
def test_service_status_display_colors_and_optional_metrics(prog,services):
    ui=progress.StatusDisplay()
    ui.console=MagicMock()
    ui.show_service_status(services)
    ui.console.print.assert_called_once()

@pytest.mark.parametrize("statuses",[
    ["running","stopped","deploying","error","unknown"],[],["paused"],
])
def test_deployment_status_display_all_phases(prog,statuses):
    ui=progress.StatusDisplay()
    ui.console=MagicMock()
    ui.show_deployment_status({f"app-{i}":{"status":state,"version":"1.2","url":"/","last_updated":"now"} for i,state in enumerate(statuses)})
    ui.console.print.assert_called_once()

@pytest.mark.parametrize("cpu,mem,disk,load", [
    (15,25,45,.5),(75,80,85,1.5),(95,98,99,2.5),
])
def test_system_metric_display_all_thresholds(prog,cpu,mem,disk,load):
    ui=progress.StatusDisplay()
    ui.console=MagicMock()
    ui.show_system_metrics({"cpu_percent":cpu,"memory_percent":mem,"disk_percent":disk,"load_average":[load,0,0],"connections":6})
    ui.console.print.assert_called_once()

@pytest.mark.parametrize("value,expected",[
    (0,"green"),(69.9,"green"),(70,"yellow"),(84.9,"yellow"),(85,"red"),(100,"red")
])
def test_usage_threshold_styles(prog,value,expected):
    ui=progress.StatusDisplay()
    assert expected in ui._get_usage_status(value)

@pytest.mark.parametrize("value,expected",[
    (0,"green"),(.9,"green"),(1,"yellow"),(1.99,"yellow"),(2,"red"),(10,"red")
])
def test_load_threshold_styles(prog,value,expected):
    ui=progress.StatusDisplay()
    assert expected in ui._get_load_status(value)

def test_show_progress_convenience_context(monkeypatch):
    status=MagicMock()
    monkeypatch.setattr(progress.ProgressManager,"spinner",lambda *a,**kw:nullcontext(status))
    with progress.show_progress("Checking") as current: assert current is status

def test_step_progress_preserves_execution_order(prog,monkeypatch):
    pm,p=prog
    monkeypatch.setattr(progress,"ProgressManager",lambda:pm)
    result=progress.show_step_progress(["validate","build","start"],lambda name:name.upper())
    assert result==["VALIDATE","BUILD","START"]
    assert p.advance.call_count==3

@pytest.mark.parametrize("steps",[None,[],["fetch","compile","start"]])
def test_simulated_long_operation_both_modes(prog,monkeypatch,steps):
    pm,p=prog
    monkeypatch.setattr(progress,"ProgressManager",lambda:pm)
    monkeypatch.setattr(progress,"show_progress",lambda *a,**kw:nullcontext(MagicMock()))
    progress.simulate_long_operation("test",duration=.01,steps=steps)
    if steps: assert p.advance.call_count==len(steps)


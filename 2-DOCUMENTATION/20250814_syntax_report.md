# Syntax Error Detection Report
==================================================

**Files Checked:** 282
**Files with Errors:** 15
**Total Errors:** 30
**Duration:** 0.55 seconds

## Critical Syntax Errors
------------------------------

### /home/adam/Projects/Spyder/SpyderP_PortfolioMgmt/SpyderP01_PortfolioManager.py
- **compilation_error** (Line 2895):   File "/tmp/tmpkp5x1qnu.py", line 2895
    'ytd_return': f"{metrics.ytd_return     
                    ^
SyntaxError: '{' was never closed

- **syntax_error** (Line 2895): SyntaxError: '{' was never closed
  ```python
  'ytd_return': f"{metrics.ytd_return
  ```

### /home/adam/Projects/Spyder/SpyderP_PortfolioMgmt/SpyderP02_AllocationOptimizer.py
- **compilation_error** (Line 2772):   File "/tmp/tmptd36wf1_.py", line 2772
    
    ^
SyntaxError: expected 'except' or 'finally' block

- **syntax_error** (Line 2772): SyntaxError: expected 'except' or 'finally' block

### /home/adam/Projects/Spyder/SpyderL_ML/SpyderL14_RealTimePredictor.py
- **compilation_error** (Line 835):   File "/tmp/tmpbt4u9ymd.py", line 835
    self.event_manager.subscribe(
                                ^
SyntaxError: '(' was never closed

- **syntax_error** (Line 835): SyntaxError: '(' was never closed
  ```python
  self.event_manager.subscribe(
  ```

### /home/adam/Projects/Spyder/SpyderL_ML/SpyderL12_RandomForestEnsemble.py
- **compilation_error** (Line 28): Sorry: IndentationError: unexpected indent (tmptks51awq.py, line 28)
- **syntax_error** (Line 28): SyntaxError: unexpected indent
  ```python
  from sklearn.ensemble import GradientBoostingRegressor
  ```

### /home/adam/Projects/Spyder/SpyderL_ML/SpyderL13_LSTMPricer.py
- **compilation_error** (Line 42): Sorry: IndentationError: unexpected indent (tmptdqo43uw.py, line 42)
- **syntax_error** (Line 42): SyntaxError: unexpected indent
  ```python
  from scipy.stats import norm
  ```

### /home/adam/Projects/Spyder/SpyderL_ML/SpyderL08_EntryOptimizer.py
- **compilation_error** (Line 499): Sorry: IndentationError: unindent does not match any outer indentation level (tmplgeg65pl.py, line 499)
- **syntax_error** (Line 499): SyntaxError: unindent does not match any outer indentation level
  ```python
  self._calculate_feature_importance(X_scaled, y)
  ```

### /home/adam/Projects/Spyder/SpyderX_Agents/SpyderX09_AlertManagerAgent.py
- **compilation_error** (Line 640): Sorry: IndentationError: expected an indented block after 'if' statement on line 640 (tmplxbm4dqn.py, line 646)
- **syntax_error** (Line 646): SyntaxError: expected an indented block after 'if' statement on line 640
  ```python
  def _evaluate_condition(self, condition: AlertCondition,
  ```

### /home/adam/Projects/Spyder/SpyderI_Integration/SpyderI02_EventRouter.py
- **compilation_error** (Line 1150):   File "/tmp/tmpvn0600ke.py", line 1150
    """
SyntaxError: expected 'except' or 'finally' block

- **syntax_error** (Line 1150): SyntaxError: expected 'except' or 'finally' block
  ```python
  """
  ```

### /home/adam/Projects/Spyder/SpyderZ_Communication/SpyderZ03_TradingCoordinator.py
- **compilation_error** (Line 876):   File "/tmp/tmp84ipenqq.py", line 876
    print("   • Command retry with exponential backoff")Discarding old message with sequence {sequence}")
                                                                                                       ^
SyntaxError: unterminated string literal (detected at line 876)

- **syntax_error** (Line 876): SyntaxError: unterminated string literal (detected at line 876)
  ```python
  print("   • Command retry with exponential backoff")Discarding old message with sequence {sequence}")
  ```

### /home/adam/Projects/Spyder/SpyderZ_Communication/SpyderZ06_AutoHedger.py
- **compilation_error** (Line 1130):   File "/tmp/tmpcfhu4og3.py", line 1130
    self.current_exposure.delta_dollars = greek_data.get('delta_
                                                         ^
SyntaxError: unterminated string literal (detected at line 1130)

- **syntax_error** (Line 1130): SyntaxError: unterminated string literal (detected at line 1130)
  ```python
  self.current_exposure.delta_dollars = greek_data.get('delta_
  ```

### /home/adam/Projects/Spyder/backups/import_fix_20250814_020952/SpyderB01_SpyderClient.py
- **compilation_error** (Line 67):   File "/tmp/tmpfolcvw7w.py", line 67
    from dataclasses import dataclass, field
    ^^^^
SyntaxError: invalid syntax

- **syntax_error** (Line 67): SyntaxError: invalid syntax
  ```python
  from dataclasses import dataclass, field
  ```

### /home/adam/Projects/Spyder/SpyderZ_Communication/SpyderZ04_VolatilityEngine.py
- **compilation_error** (Line 2024):   File "/tmp/tmpdk_4i_4r.py", line 2024
    def _calculate_put_theta
                            ^
SyntaxError: expected '('

- **syntax_error** (Line 2024): SyntaxError: expected '('
  ```python
  def _calculate_put_theta
  ```

### /home/adam/Projects/Spyder/SpyderN_OptionsAnalytics/SpyderN10_OptionsFlowAnalyzer.py
- **compilation_error** (Line 584):   File "/tmp/tmpvr1dt1hp.py", line 584
    """
    ^
SyntaxError: unterminated triple-quoted string literal (detected at line 587)

- **syntax_error** (Line 584): SyntaxError: unterminated triple-quoted string literal (detected at line 587)
  ```python
  """
  ```

### /home/adam/Projects/Spyder/SpyderJ_Alerts/SpyderJ01_AlertManager.py
- **compilation_error** (Line 307):   File "/tmp/tmp6cnu_jm_.py", line 307
    except Exception as e:
    ^^^^^^
SyntaxError: invalid syntax

- **syntax_error** (Line 307): SyntaxError: invalid syntax
  ```python
  except Exception as e:
  ```

### /home/adam/Projects/Spyder/SpyderG_GUI/SpyderG03_OptionChainWidget.py
- **compilation_error** (Line 36): Sorry: IndentationError: unexpected indent (tmplhly7l8i.py, line 36)
- **syntax_error** (Line 36): SyntaxError: unexpected indent
  ```python
  QLabel, QPushButton, QComboBox, QSpinBox, QCheckBox, QGroupBox
  ```

## Warnings
---------------

### /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ24_ProductionWatchdog.py
- **bracket_warning** (Line 13): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 16): Unclosed bracket: [ (expected ])
- **bracket_warning** (Line 19): Unmatched closing bracket: ]
- **bracket_warning** (Line 20): Unmatched closing bracket: )
- **bracket_warning** (Line 88): Unclosed bracket: ( (expected ))

### /home/adam/Projects/Spyder/config/config_template.py
- **bracket_warning** (Line 11): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 13): Unmatched closing bracket: )
- **bracket_warning** (Line 18): Unclosed bracket: { (expected })
- **bracket_warning** (Line 24): Unmatched closing bracket: }
- **bracket_warning** (Line 26): Unclosed bracket: { (expected })

### /home/adam/Projects/Spyder/SpyderM_Monitoring/SpyderM03_MigrationMonitor.py
- **bracket_warning** (Line 90): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 90): Unclosed bracket: { (expected })
- **bracket_warning** (Line 95): Unmatched closing bracket: }
- **bracket_warning** (Line 95): Unmatched closing bracket: )
- **bracket_warning** (Line 102): Unclosed bracket: ( (expected ))

### /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ25_SystemMonitor.py
- **bracket_warning** (Line 96): Unclosed bracket: { (expected })
- **bracket_warning** (Line 97): Unclosed bracket: { (expected })
- **bracket_warning** (Line 102): Unmatched closing bracket: }
- **bracket_warning** (Line 103): Unclosed bracket: { (expected })
- **bracket_warning** (Line 107): Unmatched closing bracket: }

### /home/adam/Projects/Spyder/SpyderM_Monitoring/__init__.py
- **bracket_warning** (Line 27): Unclosed bracket: [ (expected ])
- **bracket_warning** (Line 38): Unmatched closing bracket: ]

### /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ14_MainLauncher.py
- **bracket_warning** (Line 63): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 65): Unmatched closing bracket: )
- **bracket_warning** (Line 86): Unclosed bracket: { (expected })
- **bracket_warning** (Line 88): Unclosed bracket: { (expected })
- **bracket_warning** (Line 92): Unmatched closing bracket: }

### /home/adam/Projects/Spyder/config/config.py
- **bracket_warning** (Line 20): Unclosed bracket: { (expected })
- **bracket_warning** (Line 22): Unclosed bracket: { (expected })
- **bracket_warning** (Line 23): Unclosed bracket: { (expected })
- **bracket_warning** (Line 27): Unmatched closing bracket: }
- **bracket_warning** (Line 28): Unclosed bracket: { (expected })

### /home/adam/Projects/Spyder/SpyderM_Monitoring/SpyderM04_TradingMetrics.py
- **bracket_warning** (Line 328): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 333): Unmatched closing bracket: )
- **bracket_warning** (Line 397): Unclosed bracket: ( (expected ))
- **bracket_warning** (Line 411): Unmatched closing bracket: )
- **bracket_warning** (Line 460): Unclosed bracket: ( (expected ))

### /home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ80_VerifyDashboardIntegration.py
- **bracket_warning** (Line 39): Unclosed bracket: { (expected })
- **bracket_warning** (Line 45): Unmatched closing bracket: }
- **bracket_warning** (Line 48): Unclosed bracket: { (expected })
- **bracket_warning** (Line 55): Unmatched closing bracket: }
- **bracket_warning** (Line 58): Unclosed bracket: { (expected })

### /home/adam/Projects/Spyder/SpyderM_Monitoring/SpyderM01_SystemMonitor.py
- **bracket_warning** (Line 110): Unclosed bracket: { (expected })
- **bracket_warning** (Line 124): Unmatched closing bracket: }
- **bracket_warning** (Line 143): Unclosed bracket: { (expected })
- **bracket_warning** (Line 155): Unmatched closing bracket: }
- **bracket_warning** (Line 236): Unclosed bracket: { (expected })

## Summary Statistics
- Clean files: 17
- Files with warnings: 250
- Files with errors: 15
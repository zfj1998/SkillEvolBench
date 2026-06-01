<div align="center">
  <h1>SkillEvolBench: Benchmarking the Evolution from Episodic Experience to Procedural Skills</h1>

  <p>
    <em>Can one-off task experience become reusable instructions that future agents can follow?</em>
  </p>

  <p>
    <a href="https://arxiv.org/abs/2605.24117"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2605.24117-f8d7da?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyBpZD0ibG9nb21hcmsiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgdmlld0JveD0iMCAwIDE3LjczMiAyNC4yNjkiPjxnIGlkPSJ0aW55Ij48cGF0aCBkPSJNNTczLjU0OSwyODAuOTE2bDIuMjY2LDIuNzM4LDYuNjc0LTcuODRjLjM1My0uNDcuNTItLjcxNy4zNTMtMS4xMTdhMS4yMTgsMS4yMTgsMCwwLDAtMS4wNjEtLjc0OGgwYS45NTMuOTUzLDAsMCwwLS43MTIuMjYyWiIgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTU2Ni45ODQgLTI3MS41NDgpIiBmaWxsPSIjYmRiOWI0Ii8%2BPHBhdGggZD0iTTU3OS41MjUsMjgyLjIyNWwtMTAuNjA2LTEwLjE3NGExLjQxMywxLjQxMywwLDAsMC0uODM0LS41LDEuMDksMS4wOSwwLDAsMC0xLjAyNy42NmMtLjE2Ny40LS4wNDcuNjgxLjMxOSwxLjIwNmw4LjQ0LDEwLjI0MmgwbC02LjI4Miw3LjcxNmExLjMzNiwxLjMzNiwwLDAsMC0uMzIzLDEuMywxLjExNCwxLjExNCwwLDAsMCwxLjA0LjY5QS45OTIuOTkyLDAsMCwwLDU3MSwyOTNsOC41MTktNy45MkExLjkyNCwxLjkyNCwwLDAsMCw1NzkuNTI1LDI4Mi4yMjVaIiB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtNTY2Ljk4NCAtMjcxLjU0OCkiIGZpbGw9IiNiMzFiMWIiLz48cGF0aCBkPSJNNTg0LjMyLDI5My45MTJsLTguNTI1LTEwLjI3NSwwLDBMNTczLjUzLDI4MC45bC0xLjM4OSwxLjI1NGEyLjA2MywyLjA2MywwLDAsMCwwLDIuOTY1bDEwLjgxMiwxMC40MTlhLjkyNS45MjUsMCwwLDAsLjc0Mi4yODIsMS4wMzksMS4wMzksMCwwLDAsLjk1My0uNjY3QTEuMjYxLDEuMjYxLDAsMCwwLDU4NC4zMiwyOTMuOTEyWiIgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTU2Ni45ODQgLTI3MS41NDgpIiBmaWxsPSIjYmRiOWI0Ii8%2BPC9nPjwvc3ZnPg%3D%3D&logoColor=9f1239&labelColor=fff5f5" /></a>
    <a href="https://arxiv.org/pdf/2605.24117"><img alt="Paper PDF" src="https://img.shields.io/badge/Paper-PDF-fee2e2?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iaXNvLTg4NTktMSI%2FPg0KPCEtLSBHZW5lcmF0b3I6IEFkb2JlIElsbHVzdHJhdG9yIDE5LjAuMCwgU1ZHIEV4cG9ydCBQbHVnLUluIC4gU1ZHIFZlcnNpb246IDYuMDAgQnVpbGQgMCkgIC0tPg0KPHN2ZyB2ZXJzaW9uPSIxLjEiIGlkPSJMYXllcl8xIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB4PSIwcHgiIHk9IjBweCINCgkgdmlld0JveD0iMCAwIDUxMiA1MTIiIHN0eWxlPSJlbmFibGUtYmFja2dyb3VuZDpuZXcgMCAwIDUxMiA1MTI7IiB4bWw6c3BhY2U9InByZXNlcnZlIj4NCjxwYXRoIHN0eWxlPSJmaWxsOiNFMkU1RTc7IiBkPSJNMTI4LDBjLTE3LjYsMC0zMiwxNC40LTMyLDMydjQ0OGMwLDE3LjYsMTQuNCwzMiwzMiwzMmgzMjBjMTcuNiwwLDMyLTE0LjQsMzItMzJWMTI4TDM1MiwwSDEyOHoiLz4NCjxwYXRoIHN0eWxlPSJmaWxsOiNCMEI3QkQ7IiBkPSJNMzg0LDEyOGg5NkwzNTIsMHY5NkMzNTIsMTEzLjYsMzY2LjQsMTI4LDM4NCwxMjh6Ii8%2BDQo8cG9seWdvbiBzdHlsZT0iZmlsbDojQ0FEMUQ4OyIgcG9pbnRzPSI0ODAsMjI0IDM4NCwxMjggNDgwLDEyOCAiLz4NCjxwYXRoIHN0eWxlPSJmaWxsOiNGMTU2NDI7IiBkPSJNNDE2LDQxNmMwLDguOC03LjIsMTYtMTYsMTZINDhjLTguOCwwLTE2LTcuMi0xNi0xNlYyNTZjMC04LjgsNy4yLTE2LDE2LTE2aDM1MmM4LjgsMCwxNiw3LjIsMTYsMTYNCglWNDE2eiIvPg0KPGc%2BDQoJPHBhdGggc3R5bGU9ImZpbGw6I0ZGRkZGRjsiIGQ9Ik0xMDEuNzQ0LDMwMy4xNTJjMC00LjIyNCwzLjMyOC04LjgzMiw4LjY4OC04LjgzMmgyOS41NTJjMTYuNjQsMCwzMS42MTYsMTEuMTM2LDMxLjYxNiwzMi40OA0KCQljMCwyMC4yMjQtMTQuOTc2LDMxLjQ4OC0zMS42MTYsMzEuNDg4aC0yMS4zNnYxNi44OTZjMCw1LjYzMi0zLjU4NCw4LjgxNi04LjE5Miw4LjgxNmMtNC4yMjQsMC04LjY4OC0zLjE4NC04LjY4OC04LjgxNlYzMDMuMTUyeg0KCQkgTTExOC42MjQsMzEwLjQzMnYzMS44NzJoMjEuMzZjOC41NzYsMCwxNS4zNi03LjU2OCwxNS4zNi0xNS41MDRjMC04Ljk0NC02Ljc4NC0xNi4zNjgtMTUuMzYtMTYuMzY4SDExOC42MjR6Ii8%2BDQoJPHBhdGggc3R5bGU9ImZpbGw6I0ZGRkZGRjsiIGQ9Ik0xOTYuNjU2LDM4NGMtNC4yMjQsMC04LjgzMi0yLjMwNC04LjgzMi03Ljkydi03Mi42NzJjMC00LjU5Miw0LjYwOC03LjkzNiw4LjgzMi03LjkzNmgyOS4yOTYNCgkJYzU4LjQ2NCwwLDU3LjE4NCw4OC41MjgsMS4xNTIsODguNTI4SDE5Ni42NTZ6IE0yMDQuNzIsMzExLjA4OFYzNjguNGgyMS4yMzJjMzQuNTQ0LDAsMzYuMDgtNTcuMzEyLDAtNTcuMzEySDIwNC43MnoiLz4NCgk8cGF0aCBzdHlsZT0iZmlsbDojRkZGRkZGOyIgZD0iTTMwMy44NzIsMzEyLjExMnYyMC4zMzZoMzIuNjI0YzQuNjA4LDAsOS4yMTYsNC42MDgsOS4yMTYsOS4wNzJjMCw0LjIyNC00LjYwOCw3LjY4LTkuMjE2LDcuNjgNCgkJaC0zMi42MjR2MjYuODY0YzAsNC40OC0zLjE4NCw3LjkyLTcuNjY0LDcuOTJjLTUuNjMyLDAtOS4wNzItMy40NC05LjA3Mi03Ljkydi03Mi42NzJjMC00LjU5MiwzLjQ1Ni03LjkzNiw5LjA3Mi03LjkzNmg0NC45MTINCgkJYzUuNjMyLDAsOC45NiwzLjM0NCw4Ljk2LDcuOTM2YzAsNC4wOTYtMy4zMjgsOC43MDQtOC45Niw4LjcwNGgtMzcuMjQ4VjMxMi4xMTJ6Ii8%2BDQo8L2c%2BDQo8cGF0aCBzdHlsZT0iZmlsbDojQ0FEMUQ4OyIgZD0iTTQwMCw0MzJIOTZ2MTZoMzA0YzguOCwwLDE2LTcuMiwxNi0xNnYtMTZDNDE2LDQyNC44LDQwOC44LDQzMiw0MDAsNDMyeiIvPg0KPGc%2BDQo8L2c%2BDQo8Zz4NCjwvZz4NCjxnPg0KPC9nPg0KPGc%2BDQo8L2c%2BDQo8Zz4NCjwvZz4NCjxnPg0KPC9nPg0KPGc%2BDQo8L2c%2BDQo8Zz4NCjwvZz4NCjxnPg0KPC9nPg0KPGc%2BDQo8L2c%2BDQo8Zz4NCjwvZz4NCjxnPg0KPC9nPg0KPGc%2BDQo8L2c%2BDQo8Zz4NCjwvZz4NCjxnPg0KPC9nPg0KPC9zdmc%2BDQo%3D&logoColor=b91c1c&labelColor=fff7ed" /></a>
    <a href="https://skillevolbench.github.io/"><img alt="Project Page" src="https://img.shields.io/badge/Project-Page-dbf4ff?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB2aWV3Qm94PSIwIDAgMzIgMzIiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI%2BPGcgaWQ9IndlYnNpdGUiPjxnPjxwYXRoIGQ9Im0yOS44NCAxNmMuMTc4ODcgOS44NDI4OC0xMC40Mzc0MyAxNi41NTQzMS0xOS4zMjAwOSAxMi43Mjk4Mi0xMS4yMjczNC00Ljc4MjE3LTEwLjk3OTg2LTIxLjE3NDgyLjM4MDMxLTI1LjYxOTgyIDguODQyOTktMy40Nzk0MyAxOS4xMTQxMyAzLjIxMTg3IDE4LjkzOTc4IDEyLjg5eiIgZmlsbD0iIzk1YzdmOCIvPjxnIGZpbGw9IiMyNDVlN2MiPjxwYXRoIGQ9Im0xMy4wNSAyLjQ5YTE0LjY2MDg2IDE0LjY2MDg2IDAgMCAwIC0yLjE1LjYyIDEzLjI3MDM0IDEzLjI3MDM0IDAgMCAxIDYuOTMtLjggMTUuMjQyMjEgMTUuMjQyMjEgMCAwIDAgLTQuNzguMTh6Ii8%2BPHBhdGggZD0ibTE4LjAzIDI5LjY1YTEzLjA4Mzc0IDEzLjA4Mzc0IDAgMCAxIC03LjUxLS45MiAxNC4zNiAxNC4zNiAwIDAgMCA3LjUxLjkyeiIvPjxwYXRoIGQ9Im0xNi4yNyAyLjJoLS41NGExLjEyMjMxIDEuMTIyMzEgMCAwIDEgLjU0IDB6Ii8%2BPHBhdGggZD0ibTE2LjMgMjkuOGExLjMyMTY1IDEuMzIxNjUgMCAwIDEgLS42IDB6Ii8%2BPHBhdGggZD0ibTcuMSA1LjQxYTExLjA3MzU2IDExLjA3MzU2IDAgMCAxIDIuNTgtMS43NSAxMy44MTQyNSAxMy44MTQyNSAwIDAgMCAtMi41OCAxLjc1eiIvPjxwYXRoIGQ9Im0yNC45IDUuNDEtLjAyLjAyYTE0LjUwNTE1IDE0LjUwNTE1IDAgMCAwIC02LjMxLTMgMTIuNTE2MDYgMTIuNTE2MDYgMCAwIDEgNi4zMyAyLjk4eiIvPjxwYXRoIGQ9Im03LjEgMjYuNTlhMTQuNTEzOTQgMTQuNTEzOTQgMCAwIDAgMi4xNSAxLjUyIDEwLjg0NDc2IDEwLjg0NDc2IDAgMCAxIC0yLjE1LTEuNTJ6Ii8%2BPHBhdGggZD0ibTI0LjkgMjYuNTlhMTIuNjc1MjcgMTIuNjc1MjcgMCAwIDEgLTYuNTkgMy4wMiAxNC4zMjQzNyAxNC4zMjQzNyAwIDAgMCA2LjU3LTMuMDR6Ii8%2BPHBhdGggZD0ibTIxLjggNy40MWExMS4wMTUzNyAxMS4wMTUzNyAwIDAgMCAtMi45Mi00LjkzIDE0LjM2OTc5IDE0LjM2OTc5IDAgMCAwIC01Ljc3LS4wNGMtNS42MjI0NiA1LjI1Ni01LjM1NDUxIDIyLjI0NjM4LS4wMDAyMiAyNy4xMmExMy43MTE0NCAxMy43MTE0NCAwIDAgMCA1Ljk1MDIzLS4xYzUuMTc4MTQtNS41NzIzMiA0LjI1MjczLTE3LjYxMDQyIDIuNzM5OTktMjIuMDV6bS0xMC43NyA4LjYxYTI3LjkyOTIgMjcuOTI5MiAwIDAgMSAxLjA3LTcuOTRjMS45MjMxOC02LjQ0MzgzIDUuODg5MTUtNi4zNTQzNyA3Ljc5LjAwMDE0YTI4LjU5NTg4IDI4LjU5NTg4IDAgMCAxIDEuMSA3LjkxOTg2Yy0uMjEgMTYuMDYtOS40NCAxNy44NC05Ljk2LjAyeiIvPjxwYXRoIGQ9Im0yOS44NCAxNmMwIC4zNC0uMDEuNjctLjA0IDFoLTI3LjU2YTExLjEzMzYxIDExLjEzMzYxIDAgMCAxIDAtMmgyNy41NmMuMDMuMzMuMDQuNjYuMDQgMXoiLz48cGF0aCBkPSJtMjguMyAyMi4zOWExMy40MDEgMTMuNDAxIDAgMCAxIC0xLjI5IDJoLTIyLjA1YTEyLjU1NDczIDEyLjU1NDczIDAgMCAxIC0xLjI0MDA1LTJ6Ii8%2BPHBhdGggZD0ibTI4LjMgOS42MWgtMjQuNThhMTIuNTUyMDUgMTIuNTUyMDUgMCAwIDEgMS4yNC0yaDIyLjA1YTEzLjM5NDggMTMuMzk0OCAwIDAgMSAxLjI5IDJ6Ii8%2BPC9nPjwvZz48L2c%2BPC9zdmc%2B&logoColor=0969da&labelColor=f6f8fa" /></a>
    <a href="https://github.com/yingtie-lei/skills-evo-bench"><img alt="Code" src="https://img.shields.io/badge/GitHub-Code-eaeef2?style=for-the-badge&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iOTgiIGhlaWdodD0iOTYiIHZpZXdCb3g9IjAgMCA5OCA5NiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGcgY2xpcC1wYXRoPSJ1cmwoI2NsaXAwXzczMF8yNzEyNikiPgo8cGF0aCBkPSJNNDEuNDM5NSA2OS4zODQ4QzI4LjgwNjYgNjcuODUzNSAxOS45MDYyIDU4Ljc2MTcgMTkuOTA2MiA0Ni45OTAyQzE5LjkwNjIgNDIuMjA1MSAyMS42Mjg5IDM3LjAzNzEgMjQuNSAzMy41OTE4QzIzLjI1NTkgMzAuNDMzNiAyMy40NDczIDIzLjczNDQgMjQuODgyOCAyMC45NTlDMjguNzEwOSAyMC40ODA1IDMzLjg3ODkgMjIuNDkwMiAzNi45NDE0IDI1LjI2NTZDNDAuNTc4MSAyNC4xMTcyIDQ0LjQwNjIgMjMuNTQzIDQ5LjA5NTcgMjMuNTQzQzUzLjc4NTIgMjMuNTQzIDU3LjYxMzMgMjQuMTE3MiA2MS4wNTg2IDI1LjE2OTlDNjQuMDI1NCAyMi40OTAyIDY5LjI4OTEgMjAuNDgwNSA3My4xMTcyIDIwLjk1OUM3NC40NTcgMjMuNTQzIDc0LjY0ODQgMzAuMjQyMiA3My40MDQzIDMzLjQ5NjFDNzYuNDY2OCAzNy4xMzI4IDc4LjA5MzcgNDIuMDEzNyA3OC4wOTM3IDQ2Ljk5MDJDNzguMDkzNyA1OC43NjE3IDY5LjE5MzQgNjcuNjYyMSA1Ni4zNjkxIDY5LjI4OTFDNTkuNjIzIDcxLjM5NDUgNjEuODI0MiA3NS45ODgzIDYxLjgyNDIgODEuMjUyTDYxLjgyNDIgOTEuMjA1MUM2MS44MjQyIDk0LjA3NjIgNjQuMjE2OCA5NS43MDMxIDY3LjA4NzkgOTQuNTU0N0M4NC40MTAyIDg3Ljk1MTIgOTggNzAuNjI4OSA5OCA0OS4xOTE0Qzk4IDIyLjEwNzQgNzUuOTg4MyA2LjY5NTM5ZS0wNyA0OC45MDQzIDQuMzA5ZS0wN0MyMS44MjAzIDEuOTIyNjFlLTA3IC0xLjk0NzllLTA3IDIyLjEwNzQgLTQuMzM0M2UtMDcgNDkuMTkxNEMtNi4yMDYzMWUtMDcgNzAuNDM3NSAxMy40OTQxIDg4LjA0NjkgMzEuNjc3NyA5NC42NTA0QzM0LjI2MTcgOTUuNjA3NCAzNi43NSA5My44ODQ4IDM2Ljc1IDkxLjMwMDhMMzYuNzUgODMuNjQ0NUMzNS40MTAyIDg0LjIxODggMzMuNjg3NSA4NC42MDE2IDMyLjE1NjIgODQuNjAxNkMyNS44Mzk4IDg0LjYwMTYgMjIuMTA3NCA4MS4xNTYzIDE5LjQyNzcgNzQuNzQ0MUMxOC4zNzUgNzIuMTYwMiAxNy4yMjY2IDcwLjYyODkgMTUuMDI1NCA3MC4zNDE4QzEzLjg3NyA3MC4yNDYxIDEzLjQ5NDEgNjkuNzY3NiAxMy40OTQxIDY5LjE5MzRDMTMuNDk0MSA2OC4wNDQ5IDE1LjQwODIgNjcuMTgzNiAxNy4zMjIzIDY3LjE4MzZDMjAuMDk3NyA2Ny4xODM2IDIyLjQ5MDIgNjguOTA2MyAyNC45Nzg1IDcyLjQ0NzNDMjYuODkyNiA3NS4yMjI3IDI4LjkwMjMgNzYuNDY2OCAzMS4yOTQ5IDc2LjQ2NjhDMzMuNjg3NSA3Ni40NjY4IDM1LjIxODcgNzUuNjA1NSAzNy40MTk5IDczLjQwNDNDMzkuMDQ2OSA3MS43NzczIDQwLjI5MSA3MC4zNDE4IDQxLjQzOTUgNjkuMzg0OFoiIGZpbGw9ImJsYWNrIi8%2BCjwvZz4KPGRlZnM%2BCjxjbGlwUGF0aCBpZD0iY2xpcDBfNzMwXzI3MTI2Ij4KPHJlY3Qgd2lkdGg9Ijk4IiBoZWlnaHQ9Ijk2IiBmaWxsPSJ3aGl0ZSIvPgo8L2NsaXBQYXRoPgo8L2RlZnM%2BCjwvc3ZnPgo%3D&logoColor=24292f&labelColor=f6f8fa" /></a>
  </p>

  <p>
    <sub><strong>
      Yingtie&nbsp;Lei<sup>1,*</sup>, Zhongwei&nbsp;Wan<sup>1,*</sup>, Jiankun&nbsp;Zhang<sup>2</sup>, Samiul&nbsp;Alam<sup>1</sup>, Zixuan&nbsp;Zhong<sup>3</sup>, Peizhou&nbsp;Huang<sup>4</sup>, Xin&nbsp;Wang<sup>1</sup><br />
      Jingxuan&nbsp;Zhang<sup>1</sup>, Donghao&nbsp;Zhou<sup>5</sup>, Yunta&nbsp;Hsieh<sup>4</sup>, Zhihao&nbsp;Dou<sup>6</sup>, Hui&nbsp;Shen<sup>4</sup>, Yan&nbsp;Xu<sup>7</sup>, Dimitrios&nbsp;Dimitriadis<sup>7</sup>, Tuo&nbsp;Zhang<sup>7</sup>, Mi&nbsp;Zhang<sup>1</sup>
    </strong></sub>
  </p>

  <p>
    <sub>
      <sup>1</sup>The Ohio State University,
      <sup>2</sup>The University of Chicago,
      <sup>3</sup>University College London,
      <sup>4</sup>University of Michigan,<br />
      <sup>5</sup>The Chinese University of Hong Kong,
      <sup>6</sup>Case Western Reserve University,
      <sup>7</sup>Amazon<br />
      <sup>*</sup>Equal contribution
    </sub>
  </p>

  <p><strong>SkillEvolBench Team</strong></p>

  <p>
    <sub>
      Correspondence: Tuo Zhang <a href="mailto:tuozhang@amazon.com">tuozhang@amazon.com</a>,
      Mi Zhang <a href="mailto:mizhang.1@osu.edu">mizhang.1@osu.edu</a>
    </sub>
  </p>

  <p>
    <img src="asset/osu2.png" alt="The Ohio State University" height="42" />
    &nbsp;&nbsp;&nbsp;&nbsp;
    <img src="asset/amazon.png" alt="Amazon Science" height="38" />
  </p>
</div>

## 🌟 Overview

**SkillEvolBench** is a benchmark for studying how coding agents turn short-lived execution experience into reusable procedural skills. The released repository focuses on one goal: **run the benchmark from source with reproducible configs**.

## 🗂️ GitHub Repo Layout

| Path | Purpose |
| --- | --- |
| `benchmark/tasks/` | 180 benchmark tasks with task metadata, instructions, environments, and validation assets. |
| `benchmark/skills/` | Curated seed skills used by curated-skill baselines. |
| `configs/baselines/` | Baseline YAMLs. Select with `--baseline-name <name>`. |
| `configs/models/` | Model/provider presets for Azure OpenAI, AWS Bedrock Claude, Gemini, and Kimi-style endpoints. Select with `--model-yaml`. |
| `configs/strategies/` | Runtime strategies, mainly `chain` and `chain_tier3`. Most baselines choose this automatically. |
| `configs/env_orders.yaml` | Deterministic environment orders for seeds `A`, `B`, and `C`. |
| `skillevolbench/` | Core benchmark engine: scheduler, runtime, stores, retrieval, prompting, metrics, schemas, and Harbor hooks. |
| `agents_port/` | Preinstalled-agent adapter layer for `codex`, `claude-code`, `gemini-cli`, and `kimi-cli`. |
| `scripts/run.py` | Main single-run launcher. Use this for individual reproductions. |
| `scripts/launch_main_experiment.py` | Batch launcher for canonical baselines. |
| `scripts/launch_multi_model.py` | Batch launcher for baseline × model sweeps. |
| `scripts/validate_configs.py` | Validates YAML configs against schemas. |
| `scripts/validate_assets.py` | Validates benchmark task and skill assets. |
| `scripts/preflight.py` | Checks runtime readiness before expensive model calls. |
| `scripts/summarize.py` | Summarizes a completed run. |
| `docker/agent-build/` | Builds the Harbor task image `agent-runtime:latest`. |
| `workspace/runs/` | Local generated run outputs. Do not commit. |
| `asset/` | README/project visual assets. |

## 🧩 Benchmark Structure

SkillEvolBench uses a fixed stratified design:

```text
6 environments × 5 latent skill families × 6 tasks = 180 tasks
```

For each latent skill family, `T1-T3` are learning/acquisition tasks and `T4-T6` are frozen evaluation tasks:

| Task | Role | Purpose |
| --- | --- | --- |
| `T1` | learning | canonical first encounter |
| `T2` | learning | enriched follow-up |
| `T3` | learning | variant acquisition case |
| `T4` | evaluation | context shift |
| `T5` | evaluation | adversarial variant |
| `T6` | evaluation | skill composition |

## ⚙️ Installation

Python 3.12 is recommended.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m pip install litellm boto3 jinja2 pandas matplotlib
```

Install Harbor and build the task runtime image:

```bash
python -m pip install git+https://github.com/harbor-framework/harbor.git
bash docker/agent-build/build.sh
docker image inspect agent-runtime:latest
```

## 🔐 API Keys and Provider Setup

Create a local credential file. It is ignored by Git.

```bash
touch .harbor-agents.env
chmod 600 .harbor-agents.env
```

Fill only the providers you plan to run:

```bash
# Azure OpenAI / Codex presets
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1
AZURE_OPENAI_API_KEY=<your-azure-openai-key>
# Optional if your endpoint requires it:
# AZURE_OPENAI_API_VERSION=<api-version>

# AWS Bedrock Claude presets
AWS_BEARER_TOKEN_BEDROCK=<your-bedrock-bearer-token>
AWS_REGION=us-east-1
CLAUDE_CODE_USE_BEDROCK=1

# Gemini direct presets
GEMINI_API_KEY=<your-gemini-api-key>

# Kimi / OpenAI-compatible Mantle endpoint
KIMI_BEDROCK_BASE_URL=<your-openai-compatible-base-url>
KIMI_BEDROCK_API_KEY=<your-kimi-key>
```

Load credentials in the same shell before launching runs:

```bash
set -a
source .harbor-agents.env
set +a
```

Check without printing secret values:

```bash
python -c "import os; [print(k, bool(os.getenv(k))) for k in ['AZURE_OPENAI_ENDPOINT','AZURE_OPENAI_API_KEY','AWS_BEARER_TOKEN_BEDROCK','AWS_REGION','GEMINI_API_KEY','KIMI_BEDROCK_BASE_URL','KIMI_BEDROCK_API_KEY']]"
```

### Provider notes

| Provider family | Presets | Required env vars | Notes |
| --- | --- | --- | --- |
| Azure OpenAI Codex | `gpt-5.2-codex`, `gpt-5.3-codex`, `gpt-5.4` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | The preset `agent_model_name` must match your Azure deployment name. Edit the YAML if your deployment differs. |
| AWS Bedrock Claude | `claude-sonnet-*`, `claude-opus-*` | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `CLAUDE_CODE_USE_BEDROCK=1` | Uses Bedrock inference-profile IDs such as `us.anthropic...`. Your AWS account must have model access. |
| Gemini direct | `gemini-*` | `GEMINI_API_KEY` | Included for convenience; adapt the YAML if your Gemini CLI setup differs. |
| Kimi/Mantle | `kimi-*` | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` | Requires an OpenAI-compatible endpoint. |

The paper configuration here uses **Azure OpenAI** for Codex-style models and **AWS Bedrock Claude** for Claude. If you use direct OpenAI/Anthropic API keys instead, add a new YAML under `configs/models/` and set the right `provider`, `harbor_agent_name`, `agent_model_name`, `agent_env`, and `host_litellm` fields for your endpoint.

## ✅ Validate Before Running

```bash
python -m scripts.validate_configs
python -m scripts.validate_assets
python -m scripts.preflight
python -m scripts.run --baseline-name no_skill --order-seed A --dry-run
```

A healthy dry run schedules 180 tasks and does not call any model API.

For a stricter check including Harbor and Docker image readiness:

```bash
python -m scripts.preflight --strict
```

## 🚀 Run One Benchmark

General pattern:

```bash
python -m scripts.run \
  --baseline-name <baseline_name> \
  --model-yaml configs/models/<model_preset>.yaml \
  --order-seed A
```

Azure OpenAI example:

```bash
python -m scripts.run \
  --baseline-name no_skill \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A
```

AWS Bedrock Claude example:

```bash
python -m scripts.run \
  --baseline-name selfgen_experience_always \
  --model-yaml configs/models/claude-sonnet-4.6.yaml \
  --order-seed A
```

Use `--run-id` for a stable output directory:

```bash
python -m scripts.run \
  --baseline-name raw_trajectory_rag \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A \
  --run-id rawrag_gpt54_seedA
```

## 📊 Paper Baselines

Canonical baselines are defined in `skillevolbench/baselines/policy.py`.

| Baseline | Config name | What it tests |
| --- | --- | --- |
| No Skill | `no_skill` | Bare agent with no skills, memory, or trajectory retrieval. |
| Raw Trajectory RAG | `raw_trajectory_rag` | Retrieves same-family raw learning trajectories instead of distilled skills. |
| Self-Generated Zero-Shot | `selfgen_zero_shot` | Creates skills before experience from task/family context. |
| Self-Generated Experience | `selfgen_experience_always` | Induces skills from experience and revises on every learning trial. |
| Curated Static | `curated_static` | Uses curated seed skills without revision. |
| Curated + Revision | `curated_with_revision_always` | Starts from curated skills and revises on every learning trial. |

Run the full canonical ladder for one model:

```bash
MODEL=configs/models/gpt-5.4.yaml
BASELINES=(
  no_skill
  raw_trajectory_rag
  selfgen_zero_shot
  selfgen_experience_always
  curated_static
  curated_with_revision_always
)

for BASELINE in "${BASELINES[@]}"; do
  python -m scripts.run \
    --baseline-name "$BASELINE" \
    --model-yaml "$MODEL" \
    --order-seed A
done
```

Or use the multi-run launcher after inspecting the plan:

```bash
python -m scripts.launch_multi_model \
  --baselines no_skill,raw_trajectory_rag,selfgen_zero_shot,selfgen_experience_always,curated_static,curated_with_revision_always \
  --models gpt-5.4 \
  --order-seed A \
  --max-workers 1 \
  --dry-run
```

Remove `--dry-run` to execute.

## 🧪 Ablation Baselines

| Ablation | Config name |
| --- | --- |
| Failure-only self-generated revision | `selfgen_experience` |
| Failure-only curated revision | `curated_with_revision` |
| Required Tier-3 skill files, self-generated | `selfgen_experience_always_with_tier3` |
| Required Tier-3 skill files, curated | `curated_with_revision_always_with_tier3` |

Run an ablation like any other baseline:

```bash
python -m scripts.run \
  --baseline-name selfgen_experience \
  --model-yaml configs/models/gpt-5.4.yaml \
  --order-seed A
```

## 🤖 Model Presets

| Model preset | Provider route | Credentials |
| --- | --- | --- |
| `gpt-5.2-codex.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `gpt-5.3-codex.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `gpt-5.4.yaml` | Azure OpenAI Codex CLI | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| `claude-sonnet-4.5.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-sonnet-4.6.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-opus-4.5.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `claude-opus-4.6.yaml` | AWS Bedrock Claude Code | `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION` |
| `gemini-2.5-pro.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `gemini-3-flash.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `gemini-3.1-pro.yaml` | Gemini CLI direct | `GEMINI_API_KEY` |
| `kimi-2-thinking.yaml` | OpenAI-compatible Mantle/Kimi | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` |
| `kimi-2.5.yaml` | OpenAI-compatible Mantle/Kimi | `KIMI_BEDROCK_BASE_URL`, `KIMI_BEDROCK_API_KEY` |

Inspect a preset before editing:

```bash
sed -n '1,120p' configs/models/gpt-5.4.yaml
```

## 📦 Outputs

Runs are written to:

```text
workspace/runs/<run_id>/
```

Key files:

| Path | Meaning |
| --- | --- |
| `config.json` | Frozen run configuration. |
| `reports/full_report.json` | Main metrics report. |
| `stores/replay/` | Per-task replay records. |
| `stores/events/` | Runtime event logs. |
| `stores/retrieval/` | Retrieval traces when enabled. |
| `runtime/` | Per-task execution workdirs. |
| `harbor-job/` | Harbor job artifacts. |

Summarize a run:

```bash
python -m scripts.summarize workspace/runs/<run_id>
```

Find recent runs:

```bash
ls -lt workspace/runs | head
```

## 🛠️ Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Please set an Auth method... GEMINI_API_KEY` | `.harbor-agents.env` was not sourced or `GEMINI_API_KEY` is missing. | Source `.harbor-agents.env` in the same shell. |
| `No module named 'harbor'` | Harbor SDK is missing. | `python -m pip install git+https://github.com/harbor-framework/harbor.git` |
| `agent-runtime:latest` missing | Docker image has not been built. | `bash docker/agent-build/build.sh` |
| Azure 401/403 | Endpoint/key/deployment mismatch. | Check `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `agent_model_name`. |
| Bedrock model identifier error | Region/profile mismatch. | Use the `us.anthropic...` model IDs in `configs/models/claude-*.yaml` and set `AWS_REGION`. |

## 📚 Citation

```bibtex
@article{lei2026skillevolbench,
  title={SkillEvolBench: Benchmarking the Evolution from Episodic Experience to Procedural Skills},
  author={Lei, Yingtie and Wan, Zhongwei and Zhang, Jiankun and Alam, Samiul and Zhong, Zixuan and Huang, Peizhou and Wang, Xin and Zhang, Jingxuan and Zhou, Donghao and Hsieh, Yunta and others},
  journal={arXiv preprint arXiv:2605.24117},
  year={2026}
}
```

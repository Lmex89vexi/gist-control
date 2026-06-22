"""All Textual CSS for the application. Kept in one module for easy theming."""

APP_CSS = """
Screen {
    background: #1a1b26;
}

MainScreen {
    layout: vertical;
}

#search-row {
    dock: top;
    height: 3;
    padding: 0 1;
    align: center middle;
}

#search-input {
    width: 60%;
}

#refresh-btn {
    width: 12;
    margin-left: 1;
}

#filter-bar {
    dock: top;
    height: 1;
    padding: 0 1;
    color: #565f89;
}

#filter-bar Label {
    padding: 0 1;
}

#gist-count {
    dock: top;
    height: 1;
    padding: 0 1;
    color: #565f89;
}

DataTable {
    height: 1fr;
    margin: 0 1;
}

DataTable > .datatable--header {
    color: #7aa2f7;
    background: #1f2335;
}

DataTable > .datatable--cursor {
    background: #3b4261;
}

Footer {
    background: #1f2335;
    color: #a9b1d6;
}

.detail-container {
    layout: vertical;
    height: 100%;
}

.detail-header {
    dock: top;
    height: 3;
    padding: 0 1;
    align: center middle;
}

.detail-header Label {
    width: 1fr;
}

.detail-body {
    height: 1fr;
}

.detail-meta {
    dock: bottom;
    height: 4;
    padding: 0 1;
    background: #1f2335;
}

.detail-files {
    width: 20;
    dock: left;
    background: #1f2335;
}

.detail-content {
    height: 1fr;
}

.detail-actions {
    dock: bottom;
    height: 3;
    padding: 0 1;
    align: center middle;
}

.detail-actions Button {
    margin: 0 1;
}

.filter-dialog {
    width: 50;
    height: auto;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
    margin: 1 2;
}

.filter-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.filter-dialog Input,
.filter-dialog Select {
    margin-bottom: 1;
}

.filter-dialog > Horizontal {
    height: 3;
    align: center middle;
}

.filter-dialog Button {
    margin: 0 1;
}

.edit-dialog {
    width: 80%;
    height: 85%;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
}

.edit-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.edit-dialog Input {
    margin-bottom: 1;
}

#edit-files {
    height: 1fr;
    border: solid #3b4261;
    margin-bottom: 1;
}

#edit-actions {
    dock: bottom;
    height: 3;
    align: center middle;
}

#edit-actions Button {
    margin: 0 1;
}

.stats-dialog {
    width: 60;
    height: auto;
    padding: 1 2;
    background: #1f2335;
    border: thick #565f89;
}

.stats-dialog > .title {
    text-style: bold;
    color: #7aa2f7;
    padding-bottom: 1;
}

.stats-dialog > .stat-row {
    height: 1;
    padding: 0 1;
}

.stats-dialog Button {
    dock: bottom;
    margin-top: 1;
    align: center middle;
}

#file-tabs {
    height: 100%;
}

Label.loading {
    color: #565f89;
    text-style: italic;
}

Button {
    background: #3b4261;
    color: #a9b1d6;
}

Button:hover {
    background: #565f89;
}

Button.-primary {
    background: #7aa2f7;
    color: #1a1b26;
}

Button.-error {
    background: #f7768e;
    color: #1a1b26;
}

#empty-state {
    align: center middle;
    height: 1fr;
    color: #565f89;
}

TextArea {
    background: #1f2335;
    color: #a9b1d6;
}

Select {
    background: #1f2335;
}
"""

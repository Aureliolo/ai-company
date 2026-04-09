variable "src" {
  type    = string
  default = "file://src/synthorg/persistence/sqlite/schema.sql"
}

env "sqlite" {
  src = var.src
  dev = "sqlite://file?mode=memory"
  migration {
    dir = "file://src/synthorg/persistence/sqlite/revisions"
  }
}

env "ci" {
  src = var.src
  dev = "sqlite://file?mode=memory"
  migration {
    dir = "file://src/synthorg/persistence/sqlite/revisions"
  }
  lint {
    destructive {
      error = true
    }
  }
}

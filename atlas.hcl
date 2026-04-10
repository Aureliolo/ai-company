variable "src" {
  type    = string
  default = "file://src/synthorg/persistence/sqlite/schema.sql"
}

variable "pg_src" {
  type    = string
  default = "file://src/synthorg/persistence/postgres/schema.sql"
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

env "postgres" {
  src = var.pg_src
  dev = "docker://postgres/18/dev?search_path=public"
  migration {
    dir = "file://src/synthorg/persistence/postgres/revisions"
  }
}

env "postgres_ci" {
  src = var.pg_src
  dev = "docker://postgres/18/dev?search_path=public"
  migration {
    dir = "file://src/synthorg/persistence/postgres/revisions"
  }
  lint {
    destructive {
      error = true
    }
  }
}
